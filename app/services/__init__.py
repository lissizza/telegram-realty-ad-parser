"""
Services module initialization
"""

from app.services.telegram_service import TelegramService

# Global service instances
_telegram_service: TelegramService | None = None

def get_telegram_service() -> TelegramService:
    """Get the global telegram service instance (singleton)"""
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramService()
    return _telegram_service

def set_telegram_service(service: TelegramService) -> None:
    """Set the global telegram service instance"""
    global _telegram_service
    _telegram_service = service