# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class AIRequestOptions:
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    model_name: Optional[str] = None
    is_private: bool = False
    context_messages: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class AIResponse:
    text: str
    provider: str
    model: str
    latency_ms: float
    usage: Dict[str, int] = field(default_factory=dict)
    cached: bool = False


@runtime_checkable
class AIProvider(Protocol):
    """Abstract protocol for AI model providers in Aetheris V5."""

    name: str

    async def complete(self, options: AIRequestOptions) -> AIResponse:
        """Generate a complete text response."""
        ...

    async def stream(self, options: AIRequestOptions) -> AsyncIterator[str]:
        """Stream generated text chunks asynchronously."""
        ...

    async def health(self) -> bool:
        """Check provider connectivity and API key validity."""
        ...
