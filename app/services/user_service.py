"""
User management service for handling Telegram users
"""

import logging
from typing import List, Optional

from app.core.config import settings
from app.db.mongodb import mongodb

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing Telegram users"""

    def __init__(self):
        self._authorized_users: Optional[List[int]] = None

    async def get_authorized_users(self) -> List[int]:
        """Get list of authorized user IDs"""
        if self._authorized_users is None:
            await self._load_authorized_users()
        return self._authorized_users or []

    async def _load_authorized_users(self) -> None:
        """Load authorized users from database"""
        try:
            db = mongodb.get_database()
            users_collection = db.users

            # Get all users marked as authorized
            users = await users_collection.find({"is_authorized": True}).to_list(length=None)
            self._authorized_users = [user["user_id"] for user in users]

            # If no users in DB, use the configured user ID as fallback
            if not self._authorized_users and settings.TELEGRAM_USER_ID:
                self._authorized_users = [settings.TELEGRAM_USER_ID]
                logger.info("Using configured TELEGRAM_USER_ID as fallback")

            logger.info("Loaded %d authorized users", len(self._authorized_users))

        except Exception as e:
            logger.error("Error loading authorized users: %s", e)
            self._authorized_users = []

            # Fallback to configured user ID
            if settings.TELEGRAM_USER_ID:
                self._authorized_users = [settings.TELEGRAM_USER_ID]

    async def add_authorized_user(
        self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None
    ) -> bool:
        """Add a user to authorized users list"""
        try:
            db = mongodb.get_database()
            users_collection = db.users

            # Check if user already exists
            existing_user = await users_collection.find_one({"user_id": user_id})

            if existing_user:
                # Update existing user
                await users_collection.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "is_authorized": True,
                            "username": username,
                            "first_name": first_name,
                            "updated_at": mongodb.get_current_time(),
                        }
                    },
                )
                logger.info("Updated user %d authorization status", user_id)
            else:
                # Create new user
                await users_collection.insert_one(
                    {
                        "user_id": user_id,
                        "username": username,
                        "first_name": first_name,
                        "is_authorized": True,
                        "created_at": mongodb.get_current_time(),
                        "updated_at": mongodb.get_current_time(),
                    }
                )
                logger.info("Added new authorized user %d", user_id)

            # Refresh cache
            self._authorized_users = None
            await self._load_authorized_users()

            return True

        except Exception as e:
            logger.error("Error adding authorized user %d: %s", user_id, e)
            return False

    async def remove_authorized_user(self, user_id: int) -> bool:
        """Remove a user from authorized users list"""
        try:
            db = mongodb.get_database()
            users_collection = db.users

            await users_collection.update_one(
                {"user_id": user_id}, {"$set": {"is_authorized": False, "updated_at": mongodb.get_current_time()}}
            )

            # Refresh cache
            self._authorized_users = None
            await self._load_authorized_users()

            logger.info("Removed user %d from authorized users", user_id)
            return True

        except Exception as e:
            logger.error("Error removing authorized user %d: %s", user_id, e)
            return False

    async def is_user_authorized(self, user_id: int) -> bool:
        """Check if user is authorized"""
        authorized_users = await self.get_authorized_users()
        return user_id in authorized_users

    async def get_primary_user_id(self) -> Optional[int]:
        """Get the primary user ID (first authorized user or configured user)"""
        authorized_users = await self.get_authorized_users()

        if authorized_users:
            return authorized_users[0]

        # Fallback to configured user ID
        return settings.TELEGRAM_USER_ID


# Global instance
user_service = UserService()
















