"""
Backward-compatibility re-export.

All code that does ``from app.services.telegram_service import TelegramService``
continues to work without changes.
"""

from app.services.telegram import TelegramService

__all__ = ["TelegramService"]
