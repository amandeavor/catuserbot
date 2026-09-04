# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

from typing import Any, AsyncIterator, Callable, List, Optional, Protocol, Union, runtime_checkable


@runtime_checkable
class ITelegramTransport(Protocol):
    """Abstract protocol for MTProto transport backends in Aetheris V5."""

    async def send_message(
        self,
        chat_id: Any,
        text: str,
        reply_to: Optional[int] = None,
        parse_mode: str = "md",
        link_preview: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Send a text message to a chat."""
        ...

    async def edit_message(
        self,
        chat_id: Any,
        message_id: int,
        text: str,
        parse_mode: str = "md",
        link_preview: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Edit an existing message."""
        ...

    async def delete_messages(
        self,
        chat_id: Any,
        message_ids: Union[int, List[int]],
        **kwargs: Any,
    ) -> Any:
        """Delete one or more messages."""
        ...

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
        """Send a document, photo, video, or audio file."""
        ...

    async def download_media(
        self,
        message: Any,
        file_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **kwargs: Any,
    ) -> Optional[str]:
        """Download media attached to a message to a local file path."""
        ...

    async def get_entity(self, entity: Any) -> Any:
        """Resolve an entity (user, chat, or channel) by username, ID, or phone."""
        ...

    async def get_me(self) -> Any:
        """Return the authenticated user/account entity."""
        ...

    async def iter_messages(
        self,
        chat_id: Any,
        limit: Optional[int] = None,
        offset_id: int = 0,
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        """Iterate over messages in a chat."""
        ...

    def add_event_handler(self, callback: Callable[..., Any], event_builder: Any) -> None:
        """Register an update event handler."""
        ...

    def remove_event_handler(self, callback: Callable[..., Any], event_builder: Optional[Any] = None) -> None:
        """Remove a registered event handler."""
        ...

    def is_connected(self) -> bool:
        """Check if transport client is connected."""
        ...

    async def disconnect(self) -> None:
        """Gracefully disconnect from MTProto transport."""
        ...
