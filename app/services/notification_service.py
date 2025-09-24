"""
Notification service interface for sending messages to users.

This module provides an abstract base class for notification services and
a concrete Telegram implementation with lazy bot initialization to avoid
circular imports.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class NotificationService(ABC):
    """Abstract base class for notification services"""

    @abstractmethod
    async def send_message(
        self, user_id: int, message: str, parse_mode: Optional[str] = None, reply_markup: Optional[Any] = None
    ) -> bool:
        """Send message to user"""


class TelegramNotificationService(NotificationService):
    """Telegram implementation of notification service"""

    def __init__(self) -> None:
        self._bot: Optional[Any] = None

    async def _get_bot(self) -> Any:
        """Lazy initialization of bot to avoid circular imports"""
        if self._bot is None:
            from app.telegram_bot import telegram_bot

            self._bot = telegram_bot
        return self._bot

    async def send_message(
        self, user_id: int, message: str, parse_mode: Optional[str] = None, reply_markup: Optional[Any] = None
    ) -> bool:
        """Send message to user via Telegram bot"""
        try:
            bot = await self._get_bot()
            if bot.application:
                await bot.application.bot.send_message(
                    chat_id=user_id, text=message, parse_mode=parse_mode, reply_markup=reply_markup
                )
                return True
            return False
        except Exception as e:
            logger.error("Error sending message to user %s: %s", user_id, e)
            return False


# Global instance
notification_service = TelegramNotificationService()
