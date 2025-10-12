"""
Service for getting Telegram user information
"""

import logging
from typing import Optional, Dict, Any

from app.services import get_telegram_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class TelegramUserService:
    """Service for getting Telegram user information"""
    
    def __init__(self, client=None):
        self.client = client
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user information by Telegram user ID"""
        try:
            # Use provided client or get from service
            client = self.client
            if not client:
                telegram_service = get_telegram_service()
                if not telegram_service or not telegram_service.client:
                    logger.error("Telegram service not available")
                    return None
                client = telegram_service.client
            
            # Get user information using Telethon
            user = await client.get_entity(user_id)
            
            return {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_bot": user.bot,
                "is_premium": getattr(user, 'premium', False),
                "language_code": getattr(user, 'lang_code', None)
            }
            
        except Exception as e:
            logger.error("Error getting user by ID %s: %s", user_id, e)
            return None
    
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user information by Telegram username"""
        try:
            # Remove @ if present
            username = username.lstrip('@')
            
            # Use provided client or get from service
            client = self.client
            if not client:
                telegram_service = get_telegram_service()
                if not telegram_service or not telegram_service.client:
                    logger.error("Telegram service not available")
                    return None
                client = telegram_service.client
            
            # Get user information using Telethon
            user = await client.get_entity(username)
            
            return {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_bot": user.bot,
                "is_premium": getattr(user, 'premium', False),
                "language_code": getattr(user, 'lang_code', None)
            }
            
        except Exception as e:
            logger.error("Error getting user by username %s: %s", username, e)
            return None
    
    async def resolve_user_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Resolve user identifier (ID or username) to user information"""
        try:
            # Try to parse as integer (user ID)
            try:
                user_id = int(identifier)
                return await self.get_user_by_id(user_id)
            except ValueError:
                # Not an integer, treat as username
                return await self.get_user_by_username(identifier)
                
        except Exception as e:
            logger.error("Error resolving user identifier %s: %s", identifier, e)
            return None
