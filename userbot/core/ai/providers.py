# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from userbot.core.ai.interface import AIProvider, AIRequestOptions, AIResponse

LOG = logging.getLogger("Aetheris.AI.Providers")

try:
    import httpx
except ImportError:
    httpx = None


class MockAIProvider(AIProvider):
    """Zero-dependency mock provider for testing, air-gapped setups, and deterministic validation."""

    def __init__(self, name: str = "mock"):
        self.name = name

    async def complete(self, options: AIRequestOptions) -> AIResponse:
        t0 = time.perf_counter()
        await asyncio.sleep(0.01)
        resp_text = f"[Mock {self.name}] Echo: {options.prompt}"
        if options.context_messages:
            resp_text += f" (with {len(options.context_messages)} context items)"
        latency = (time.perf_counter() - t0) * 1000.0
        return AIResponse(
            text=resp_text,
            provider=self.name,
            model=options.model_name or "mock-model-v1",
            latency_ms=latency,
            usage={"prompt_tokens": len(options.prompt.split()), "completion_tokens": len(resp_text.split())},
        )

    async def stream(self, options: AIRequestOptions) -> AsyncIterator[str]:
        words = f"[Mock {self.name}] Stream: {options.prompt}".split()
        for word in words:
            await asyncio.sleep(0.005)
            yield word + " "

    async def health(self) -> bool:
        return True


class OpenAIProvider(AIProvider):
    """OpenAI and OpenAI-compatible (Groq, Together, DeepSeek, LocalAI) endpoint adapter."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4o-mini",
        name: str = "openai",
    ):
        self.name = name
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    async def complete(self, options: AIRequestOptions) -> AIResponse:
        if not httpx or not self.api_key:
            raise RuntimeError(f"OpenAI provider {self.name} unavailable: missing API key or httpx.")

        model = options.model_name or self.default_model
        messages: List[Dict[str, str]] = []
        if options.system_prompt:
            messages.append({"role": "system", "content": options.system_prompt})
        for msg in options.context_messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": options.prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
            "stream": False,
        }

        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        latency = (time.perf_counter() - t0) * 1000.0
        choice = data["choices"][0]
        text = choice["message"]["content"] or ""
        usage = data.get("usage", {})

        return AIResponse(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=latency,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            },
        )

    async def stream(self, options: AIRequestOptions) -> AsyncIterator[str]:
        if not httpx or not self.api_key:
            raise RuntimeError(f"OpenAI provider {self.name} unavailable.")

        model = options.model_name or self.default_model
        messages: List[Dict[str, str]] = []
        if options.system_prompt:
            messages.append({"role": "system", "content": options.system_prompt})
        for msg in options.context_messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": options.prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            ) as stream_resp:
                stream_resp.raise_for_status()
                async for line in stream_resp.aiter_lines():
                    if line.startswith("data: "):
                        body = line[6:].strip()
                        if body == "[DONE]":
                            break
                        try:
                            delta_json = json.loads(body)
                            delta = delta_json["choices"][0]["delta"]
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except Exception:
                            continue

    async def health(self) -> bool:
        if not self.api_key or not httpx:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return res.status_code == 200
        except Exception:
            return False


class ClaudeProvider(AIProvider):
    """Anthropic Claude REST API provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "claude-3-5-sonnet-20241022",
        name: str = "claude",
    ):
        self.name = name
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.default_model = default_model

    async def complete(self, options: AIRequestOptions) -> AIResponse:
        if not httpx or not self.api_key:
            raise RuntimeError("Claude provider unavailable: missing API key or httpx.")

        model = options.model_name or self.default_model
        messages = []
        for msg in options.context_messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": options.prompt})

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": options.max_tokens,
            "temperature": options.temperature,
        }
        if options.system_prompt:
            payload["system"] = options.system_prompt

        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        latency = (time.perf_counter() - t0) * 1000.0
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        return AIResponse(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=latency,
            usage={
                "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
            },
        )

    async def stream(self, options: AIRequestOptions) -> AsyncIterator[str]:
        res = await self.complete(options)
        yield res.text

    async def health(self) -> bool:
        return bool(self.api_key and httpx)


class GeminiProvider(AIProvider):
    """Google Generative AI Gemini REST API provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "gemini-1.5-flash",
        name: str = "gemini",
    ):
        self.name = name
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
        self.default_model = default_model

    async def complete(self, options: AIRequestOptions) -> AIResponse:
        if not httpx or not self.api_key:
            raise RuntimeError("Gemini provider unavailable: missing API key or httpx.")

        model = options.model_name or self.default_model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

        contents = []
        for msg in options.context_messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
        contents.append({"role": "user", "parts": [{"text": options.prompt}]})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": options.temperature,
                "maxOutputTokens": options.max_tokens,
            },
        }
        if options.system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": options.system_prompt}]}

        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        latency = (time.perf_counter() - t0) * 1000.0
        text = ""
        try:
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)
        except Exception as err:
            LOG.error(f"Error parsing Gemini response: {err}")

        usage_meta = data.get("usageMetadata", {})
        return AIResponse(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=latency,
            usage={
                "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
            },
        )

    async def stream(self, options: AIRequestOptions) -> AsyncIterator[str]:
        res = await self.complete(options)
        yield res.text

    async def health(self) -> bool:
        return bool(self.api_key and httpx)


class OllamaProvider(AIProvider):
    """Local privacy-first Ollama REST API provider."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3:latest",
        name: str = "ollama",
    ):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    async def complete(self, options: AIRequestOptions) -> AIResponse:
        if not httpx:
            raise RuntimeError("Ollama provider requires httpx.")

        model = options.model_name or self.default_model
        messages = []
        if options.system_prompt:
            messages.append({"role": "system", "content": options.system_prompt})
        for msg in options.context_messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": options.prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": options.temperature},
        }

        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        latency = (time.perf_counter() - t0) * 1000.0
        text = data.get("message", {}).get("content", "")
        return AIResponse(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=latency,
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        )

    async def stream(self, options: AIRequestOptions) -> AsyncIterator[str]:
        if not httpx:
            raise RuntimeError("Ollama provider requires httpx.")

        model = options.model_name or self.default_model
        messages = []
        if options.system_prompt:
            messages.append({"role": "system", "content": options.system_prompt})
        for msg in options.context_messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": options.prompt})

        payload = {"model": model, "messages": messages, "stream": True}

        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as stream_resp:
                stream_resp.raise_for_status()
                async for line in stream_resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except Exception:
                        continue

    async def health(self) -> bool:
        if not httpx:
            return False
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False
