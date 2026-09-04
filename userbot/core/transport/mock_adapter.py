# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

from .interface import ITelegramTransport


class MockMessage:
    def __init__(self, id: int, chat_id: Any, text: str, reply_to: Optional[int] = None):
        self.id = id
        self.chat_id = chat_id
        self.text = text
        self.reply_to = reply_to
        self.sender_id = 12345678
        self.is_group = True
        self.is_private = False
        self.media = None


class MockTransportAdapter(ITelegramTransport):
    """In-memory MTProto transport adapter for high-speed offline automated testing."""

    def __init__(self):
        self._connected: bool = True
        self._messages: Dict[int, MockMessage] = {}
        self._handlers: List[Tuple[Callable[..., Any], Any]] = []
        self._counter: int = 1000
        self.sent_messages: List[MockMessage] = []
        self.edited_messages: List[MockMessage] = []
        self.deleted_message_ids: List[int] = []

    async def connect(self) -> None:
        self._connected = True

    async def send_message(
        self,
        chat_id: Any,
        text: str,
        reply_to: Optional[int] = None,
        parse_mode: str = "md",
        link_preview: bool = True,
        **kwargs: Any,
    ) -> MockMessage:
        self._counter += 1
        msg = MockMessage(self._counter, chat_id, text, reply_to)
        self._messages[self._counter] = msg
        self.sent_messages.append(msg)
        return msg

    async def edit_message(
        self,
        chat_id: Any,
        message_id: int,
        text: str,
        parse_mode: str = "md",
        link_preview: bool = True,
        **kwargs: Any,
    ) -> MockMessage:
        if message_id in self._messages:
            msg = self._messages[message_id]
            msg.text = text
            self.edited_messages.append(msg)
            return msg
        msg = MockMessage(message_id, chat_id, text)
        self._messages[message_id] = msg
        self.edited_messages.append(msg)
        return msg

    async def delete_messages(
        self,
        chat_id: Any,
        message_ids: Union[int, List[int]],
        **kwargs: Any,
    ) -> int:
        ids = [message_ids] if isinstance(message_ids, int) else list(message_ids)
        deleted = 0
        for mid in ids:
            self.deleted_message_ids.append(mid)
            if mid in self._messages:
                del self._messages[mid]
                deleted += 1
        return deleted

    async def send_file(
        self,
        chat_id: Any,
        file: Any,
        caption: str = "",
        reply_to: Optional[int] = None,
        parse_mode: str = "md",
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **kwargs: Any,
    ) -> MockMessage:
        return await self.send_message(chat_id, f"[FILE: {file}] {caption}", reply_to=reply_to)

    async def download_media(
        self,
        message: Any,
        file_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **kwargs: Any,
    ) -> Optional[str]:
        return file_path or "/tmp/mock_download.bin"

    async def get_entity(self, entity: Any) -> Any:
        class Entity:
            id = 999999
            first_name = "Mock"
            username = "mockuser"
        return Entity()

    async def get_me(self) -> Any:
        class Me:
            id = 12345678
            first_name = "Aetheris Master"
            username = "aetheris_user"
        return Me()

    async def iter_messages(
        self,
        chat_id: Any,
        limit: Optional[int] = None,
        offset_id: int = 0,
        **kwargs: Any,
    ) -> AsyncIterator[MockMessage]:
        count = 0
        for msg in reversed(list(self._messages.values())):
            if limit and count >= limit:
                break
            if msg.chat_id == chat_id:
                yield msg
                count += 1

    def add_event_handler(self, callback: Callable[..., Any], event_builder: Any) -> None:
        self._handlers.append((callback, event_builder))

    def remove_event_handler(self, callback: Callable[..., Any], event_builder: Optional[Any] = None) -> None:
        self._handlers = [h for h in self._handlers if h[0] != callback]

    def is_connected(self) -> bool:
        return self._connected

    async def disconnect(self) -> None:
        self._connected = False


MockAdapter = MockTransportAdapter
