# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, Optional, Set

LOG = logging.getLogger("Aetheris.Callbacks")


@dataclass
class CallbackToken:
    token: str
    action: str
    payload: Dict[str, Any]
    allowed_user_ids: Set[int]
    expires_at: float
    single_use: bool = False
    created_at: float = field(default_factory=time.time)


class SecureCallbackManager:
    """
    Cryptographically secure, opaque callback manager for Aetheris V5.
    Prevents callback spoofing, parameter tampering, and unauthorized invocation.
    """

    def __init__(self, default_ttl: float = 900.0):
        self.default_ttl = default_ttl
        self._tokens: Dict[str, CallbackToken] = {}
        self._handlers: Dict[str, Callable[[Any, CallbackToken], Coroutine[Any, Any, None]]] = {}
        self._lock = asyncio.Lock()

    def register_handler(
        self, action: str, handler: Callable[[Any, CallbackToken], Coroutine[Any, Any, None]]
    ) -> None:
        """Register an action handler for callbacks."""
        self._handlers[action] = handler

    def create_token(
        self,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
        allowed_user_ids: Optional[Set[int]] = None,
        ttl: Optional[float] = None,
        single_use: bool = False,
    ) -> str:
        """
        Generate an opaque token mapped to server-side metadata.
        Returns a byte-safe string formatted as `cb:<id>` suitable for Telegram inline buttons (<=64 bytes).
        """
        self._prune_expired()
        token_id = secrets.token_urlsafe(9)  # ~12 characters
        token_str = f"cb:{token_id}"
        expiry = time.time() + (ttl if ttl is not None else self.default_ttl)

        self._tokens[token_str] = CallbackToken(
            token=token_str,
            action=action,
            payload=payload or {},
            allowed_user_ids=allowed_user_ids or set(),
            expires_at=expiry,
            single_use=single_use,
        )
        return token_str

    def _prune_expired(self) -> None:
        """Remove stale callback tokens to prevent memory growth."""
        now = time.time()
        expired_keys = [k for k, tok in self._tokens.items() if tok.expires_at < now]
        for k in expired_keys:
            self._tokens.pop(k, None)

    async def handle_callback_query(self, event: Any) -> bool:
        """
        Intercept and process incoming Telegram CallbackQuery event.
        Returns True if handled, False if not an Aetheris secure token.
        """
        raw_data = getattr(event, "data", b"")
        if isinstance(raw_data, bytes):
            try:
                data_str = raw_data.decode("utf-8")
            except UnicodeDecodeError:
                return False
        else:
            data_str = str(raw_data)

        if not data_str.startswith("cb:"):
            return False

        async with self._lock:
            self._prune_expired()
            token_obj = self._tokens.get(data_str)

        if not token_obj:
            try:
                await event.answer("⚠️ This button session has expired or is invalid.", alert=True)
            except Exception:
                pass
            return True

        # Check expiration
        if time.time() > token_obj.expires_at:
            async with self._lock:
                self._tokens.pop(data_str, None)
            try:
                await event.answer("⚠️ Session expired. Please re-run the command.", alert=True)
            except Exception:
                pass
            return True

        # Check user authorization
        sender_id = getattr(event, "sender_id", None)
        if sender_id is None and hasattr(event, "query"):
            sender_id = getattr(event.query, "user_id", None)

        if token_obj.allowed_user_ids and sender_id not in token_obj.allowed_user_ids:
            try:
                await event.answer("⛔ Access Denied: You cannot trigger this action.", alert=True)
            except Exception:
                pass
            return True

        # If single-use, remove token
        if token_obj.single_use:
            async with self._lock:
                self._tokens.pop(data_str, None)

        handler = self._handlers.get(token_obj.action)
        if not handler:
            LOG.error(f"No callback handler registered for action '{token_obj.action}'")
            try:
                await event.answer("⚠️ No handler configured for this action.", alert=True)
            except Exception:
                pass
            return True

        try:
            await handler(event, token_obj)
        except Exception as err:
            LOG.exception(f"Error handling callback {token_obj.action}: {err}")
            try:
                await event.answer(f"❌ Execution error: {err}", alert=True)
            except Exception:
                pass

        return True


secure_callbacks = SecureCallbackManager()
