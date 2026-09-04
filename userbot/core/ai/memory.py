# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ChatMessage:
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float = field(default_factory=time.time)


class ConversationMemory:
    """
    Tiered memory engine for Aetheris V5 AI conversations.
    L0: Immediate request
    L1: Short-term sliding window of recent messages
    L2: Summarized context state
    """

    def __init__(self, max_history_per_chat: int = 10):
        self.max_history = max_history_per_chat
        self._conversations: Dict[str, deque] = {}
        self._summaries: Dict[str, str] = {}
        self._enabled: bool = True

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def add_turn(self, chat_key: str, user_text: str, assistant_text: str) -> None:
        if not self._enabled:
            return

        if chat_key not in self._conversations:
            self._conversations[chat_key] = deque(maxlen=self.max_history)

        dq = self._conversations[chat_key]
        dq.append(ChatMessage("user", user_text))
        dq.append(ChatMessage("assistant", assistant_text))

    def get_context(self, chat_key: str) -> List[Dict[str, str]]:
        if not self._enabled:
            return []

        messages = []
        # Include summary if present
        if chat_key in self._summaries:
            messages.append({"role": "system", "content": f"Context Summary: {self._summaries[chat_key]}"})

        if chat_key in self._conversations:
            for msg in self._conversations[chat_key]:
                messages.append({"role": msg.role, "content": msg.content})

        return messages

    def clear(self, chat_key: Optional[str] = None) -> None:
        if chat_key:
            self._conversations.pop(chat_key, None)
            self._summaries.pop(chat_key, None)
        else:
            self._conversations.clear()
            self._summaries.clear()


ai_memory = ConversationMemory()
