# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Callable, Coroutine, Dict, List, Optional

from userbot.core.ai.interface import AIProvider, AIRequestOptions, AIResponse
from userbot.core.ai.memory import ConversationMemory, ai_memory
from userbot.core.ai.providers import (
    ClaudeProvider,
    GeminiProvider,
    MockAIProvider,
    OllamaProvider,
    OpenAIProvider,
)

LOG = logging.getLogger("Aetheris.AI.Router")


class ProviderCircuit:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.last_failure_time = 0.0

    @property
    def is_open(self) -> bool:
        if self.failures >= self.failure_threshold:
            if time.time() - self.last_failure_time > self.cooldown_seconds:
                # Half-open probe
                return False
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0

    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure_time = time.time()


class AIRouterV5:
    """
    Central AI Router for Aetheris V5.
    Provides intelligent provider dispatch, automated fallback cascades,
    per-provider circuit breaking, and debounced Telegram message streaming.
    """

    def __init__(self, memory: Optional[ConversationMemory] = None):
        self.memory = memory or ai_memory
        self.providers: Dict[str, AIProvider] = {}
        self.circuits: Dict[str, ProviderCircuit] = {}
        self.default_order: List[str] = []
        self._init_defaults()

    def _init_defaults(self) -> None:
        # Register standard providers
        self.register_provider(GeminiProvider())
        self.register_provider(OpenAIProvider())
        self.register_provider(ClaudeProvider())
        self.register_provider(OllamaProvider())
        self.register_provider(MockAIProvider())
        self.default_order = ["gemini", "openai", "claude", "ollama", "mock"]

    def register_provider(self, provider: AIProvider) -> None:
        self.providers[provider.name] = provider
        self.circuits[provider.name] = ProviderCircuit()

    def set_priority_order(self, order: List[str]) -> None:
        self.default_order = [p for p in order if p in self.providers]

    async def complete(
        self,
        options: Any,
        preferred_provider: Optional[str] = None,
        chat_key: Optional[str] = None,
        provider: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AIResponse:
        """
        Execute completion with automatic fallback cascade.
        Accepts either an AIRequestOptions instance or a plain prompt string.
        """
        if isinstance(options, str):
            req_options = AIRequestOptions(
                prompt=options,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        else:
            req_options = options

        pref = provider or preferred_provider

        # Inject conversational memory if chat_key is provided
        if chat_key and not req_options.context_messages:
            req_options.context_messages = self.memory.get_context(chat_key)

        candidates: List[str] = []
        if pref and pref in self.providers:
            candidates.append(pref)
        for p in self.default_order:
            if p not in candidates and p in self.providers:
                candidates.append(p)

        last_error: Optional[Exception] = None
        for p_name in candidates:
            circuit = self.circuits[p_name]
            if circuit.is_open:
                LOG.warning(f"AI Provider {p_name} is circuit-broken (skipping)")
                continue

            provider = self.providers[p_name]
            try:
                LOG.info(f"Dispatching AI request to provider: {p_name}")
                response = await provider.complete(req_options)
                circuit.record_success()

                if chat_key:
                    self.memory.add_turn(chat_key, req_options.prompt, response.text)

                return response
            except Exception as err:
                circuit.record_failure()
                last_error = err
                LOG.warning(f"AI Provider {p_name} failed: {err}. Cascading to next candidate.")

        raise RuntimeError(f"All AI providers in cascade failed. Last error: {last_error}")

    async def stream_to_telegram(
        self,
        options: AIRequestOptions,
        edit_callback: Callable[[str], Coroutine[Any, Any, Any]],
        debounce_interval: float = 1.5,
        chat_key: Optional[str] = None,
        preferred_provider: Optional[str] = None,
    ) -> str:
        """
        Stream LLM output with rate-limit protected debouncing to Telegram.
        Avoids FLOOD_WAIT by batching edits.
        """
        if chat_key and not options.context_messages:
            options.context_messages = self.memory.get_context(chat_key)

        target_provider_name = preferred_provider or (self.default_order[0] if self.default_order else "mock")
        provider = self.providers.get(target_provider_name)
        if not provider or self.circuits[target_provider_name].is_open:
            # Fall back to completion
            res = await self.complete(options, preferred_provider=target_provider_name, chat_key=chat_key)
            await edit_callback(res.text)
            return res.text

        accumulated_text = ""
        last_edit_time = 0.0
        last_sent_text = ""

        try:
            async for chunk in provider.stream(options):
                accumulated_text += chunk
                now = time.time()
                if (now - last_edit_time >= debounce_interval) and (len(accumulated_text) - len(last_sent_text) >= 15):
                    try:
                        await edit_callback(accumulated_text + " ▌")
                        last_sent_text = accumulated_text
                        last_edit_time = now
                    except Exception as tg_err:
                        LOG.debug(f"Debounced edit skipped or rate limited: {tg_err}")

            # Final edit without typing cursor
            if accumulated_text != last_sent_text:
                await edit_callback(accumulated_text)

            if chat_key:
                self.memory.add_turn(chat_key, options.prompt, accumulated_text)

            self.circuits[target_provider_name].record_success()
            return accumulated_text

        except Exception as err:
            LOG.warning(f"Streaming failed on {target_provider_name}: {err}. Falling back to complete().")
            self.circuits[target_provider_name].record_failure()
            res = await self.complete(options, chat_key=chat_key)
            await edit_callback(res.text)
            return res.text


ai_router = AIRouterV5()
