# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

from typing import Any, AsyncIterator, Callable, List, Optional, Union

from telethon import TelegramClient

from .interface import ITelegramTransport


class TelethonTransportAdapter(ITelegramTransport):
    """Production MTProto adapter for Telethon in Aetheris V5."""

    def __init__(self, client: TelegramClient):
        self._client = client

    @property
    def raw_client(self) -> TelegramClient:
        """Access underlying raw Telethon client for legacy plugins."""
        return self._client

    async def send_message(
        self,
        chat_id: Any,
        text: str,
        reply_to: Optional[int] = None,
        parse_mode: str = "md",
        link_preview: bool = True,
        **kwargs: Any,
    ) -> Any:
        return await self._client.send_message(
            chat_id,
            text,
            reply_to=reply_to,
            parse_mode=parse_mode,
            link_preview=link_preview,
            **kwargs,
        )

    async def edit_message(
        self,
        chat_id: Any,
        message_id: int,
        text: str,
        parse_mode: str = "md",
        link_preview: bool = True,
        **kwargs: Any,
    ) -> Any:
        return await self._client.edit_message(
            chat_id,
            message_id,
            text,
            parse_mode=parse_mode,
            link_preview=link_preview,
            **kwargs,
        )

    async def delete_messages(
        self,
        chat_id: Any,
        message_ids: Union[int, List[int]],
        **kwargs: Any,
    ) -> Any:
        return await self._client.delete_messages(chat_id, message_ids, **kwargs)

    async def send_file(
        self,
        chat_id: Any,
        file: Any,
        caption: str = "",
        reply_to: Optional[int] = None,
        parse_mode: str = "md",
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **kwargs: Any,
    ) -> Any:
        return await self._client.send_file(
            chat_id,
            file,
            caption=caption,
            reply_to=reply_to,
            parse_mode=parse_mode,
            progress_callback=progress_callback,
            **kwargs,
        )

    async def download_media(
        self,
        message: Any,
        file_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **kwargs: Any,
    ) -> Optional[str]:
        return await self._client.download_media(
            message,
            file=file_path,
            progress_callback=progress_callback,
            **kwargs,
        )

    async def get_entity(self, entity: Any) -> Any:
        return await self._client.get_entity(entity)

    async def get_me(self) -> Any:
        return await self._client.get_me()

    async def iter_messages(
        self,
        chat_id: Any,
        limit: Optional[int] = None,
        offset_id: int = 0,
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        async for msg in self._client.iter_messages(chat_id, limit=limit, offset_id=offset_id, **kwargs):
            yield msg

    def add_event_handler(self, callback: Callable[..., Any], event_builder: Any) -> None:
        self._client.add_event_handler(callback, event_builder)

    def remove_event_handler(self, callback: Callable[..., Any], event_builder: Optional[Any] = None) -> None:
        self._client.remove_event_handler(callback, event_builder)

    def is_connected(self) -> bool:
        return bool(self._client and self._client.is_connected())

    async def disconnect(self) -> None:
        if self._client:
            await self._client.disconnect()
