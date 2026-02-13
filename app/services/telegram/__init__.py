"""
Telegram service package — split from the monolithic TelegramService.

Public API is preserved: all external code imports TelegramService
from ``app.services.telegram`` (or the re-export in
``app.services.telegram_service``).
"""

import logging
from typing import Any, Dict, Optional

from app.services.notification_service import TelegramNotificationService
from app.services.telegram.client_manager import TelegramClientManager
from app.services.telegram.message_forwarder import MessageForwarder
from app.services.telegram.message_processor import MessageProcessor
from app.services.telegram.message_validator import MessageValidator

logger = logging.getLogger(__name__)


class TelegramService:
    """Facade that delegates to specialised sub-modules."""

    def __init__(self) -> None:
        self.client_manager = TelegramClientManager()
        self.validator = MessageValidator(self.client_manager)
        self.forwarder = MessageForwarder(self.client_manager)
        self.processor = MessageProcessor(
            self.client_manager, self.validator, self.forwarder
        )
        # Wire callbacks so the client_manager can invoke the processor
        self.client_manager.set_callbacks(
            process_message=self.processor._process_message,
            reprocess_stuck=self.processor._reprocess_stuck_messages,
        )

    # ------------------------------------------------------------------
    # Backward-compatible properties
    # ------------------------------------------------------------------

    @property
    def client(self):
        return self.client_manager.client

    @property
    def is_monitoring(self):
        return self.client_manager.is_monitoring

    @property
    def topic_cache(self):
        return self.client_manager.topic_cache

    @property
    def llm_service(self):
        return self.processor.llm_service

    @property
    def filter_service(self):
        return self.processor.filter_service

    @property
    def notification_service(self):
        return self.forwarder.notification_service

    # ------------------------------------------------------------------
    # Public API — delegates to sub-modules
    # ------------------------------------------------------------------

    def set_notification_service(self, bot: Any) -> None:
        logger.info("Setting notification service with bot instance")
        self.forwarder.notification_service = TelegramNotificationService(bot)
        self.client_manager.notification_service = self.forwarder.notification_service
        logger.info("Notification service set successfully")

    async def start_monitoring(self) -> None:
        await self.client_manager.start_monitoring()

    async def stop_monitoring(self) -> None:
        await self.client_manager.stop_monitoring()

    async def update_channel_monitoring(self) -> None:
        await self.client_manager.update_channel_monitoring()

    async def update_topic_cache(self, channel_id: int, topic_id: int) -> None:
        await self.client_manager.update_topic_cache(channel_id, topic_id)

    async def analyze_channel_structure(self, channel_id: int, limit: int = 50) -> Optional[Dict[str, Any]]:
        return await self.client_manager.analyze_channel_structure(channel_id, limit)

    async def get_status(self) -> Dict[str, Any]:
        return await self.client_manager.get_status()

    def is_connection_healthy(self) -> bool:
        return self.client_manager.is_connection_healthy()

    def get_connection_status(self) -> Dict[str, Any]:
        return self.client_manager.get_connection_status()

    async def reprocess_recent_messages(self, num_messages: int, force: bool = False, user_id: Optional[int] = None, channel_id: Optional[int] = None, stop_on_existing: bool = False) -> dict:
        return await self.processor.reprocess_recent_messages(num_messages, force, user_id, channel_id, stop_on_existing)

    async def refilter_ads(self, count: int, user_id: Optional[int] = None) -> dict:
        return await self.processor.refilter_ads(count, user_id)


__all__ = ["TelegramService"]
