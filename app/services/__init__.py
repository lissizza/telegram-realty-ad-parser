"""
Services module initialization
"""

from app.services.telegram_service import TelegramService

# Global service instances
telegram_service: TelegramService | None = None

def get_telegram_service() -> TelegramService | None:
    """Get the global telegram service instance"""
    return telegram_service

def set_telegram_service(service: TelegramService) -> None:
    """Set the global telegram service instance"""
    global telegram_service
    telegram_service = service