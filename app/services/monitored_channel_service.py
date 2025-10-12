import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from bson import ObjectId
from telethon import TelegramClient

from app.core.config import settings
from app.db.mongodb import mongodb
from app.models.monitored_channel import (
    MonitoredChannel,
    MonitoredChannelCreate,
    MonitoredChannelResponse,
)
from app.services.channel_resolver_service import ChannelResolverService

logger = logging.getLogger(__name__)


class MonitoredChannelService:
    """Service for managing monitored channels (not tied to specific users)"""

    def __init__(self):
        pass  # Don't initialize db here, get it when needed
    
    async def _get_telegram_client(self) -> Optional[TelegramClient]:
        """Get Telegram client instance"""
        try:
            from app.services import get_telegram_service
            telegram_service = get_telegram_service()
            if telegram_service and telegram_service.client:
                return telegram_service.client
            else:
                logger.error("Telegram client not available")
                return None
        except Exception as e:
            logger.error("Error getting Telegram client: %s", e)
            return None
    
    async def _resolve_channel_info(self, channel_input: str) -> Optional[dict]:
        """Resolve channel information using Telegram API"""
        try:
            client = await self._get_telegram_client()
            if not client:
                logger.error("Cannot resolve channel info: Telegram client not available")
                return None
            
            resolver = ChannelResolverService(client)
            result = await resolver.resolve_channel_info(channel_input)
            
            if result:
                logger.info("Resolved channel info: %s", result)
                return result
            else:
                logger.error("Failed to resolve channel info for: %s", channel_input)
                return None
                
        except Exception as e:
            logger.error("Error resolving channel info: %s", e)
            return None

    async def _get_db(self):
        """Get database instance"""
        # Ensure MongoDB is connected
        if mongodb.client is None:
            await mongodb.connect_to_mongo()
        
        db = mongodb.get_database()
        if db is None:
            raise Exception("Database not initialized. Make sure MongoDB is connected.")
        return db

    def _parse_channel_input(self, channel_input: str) -> Tuple[str, Optional[int], str, Optional[int], Optional[str]]:
        """
        Parse channel input and extract channel info
        
        Args:
            channel_input: Can be username (@channel), link (t.me/channel), or URL
            
        Returns:
            Tuple of (channel_username, topic_id, channel_link, channel_id, topic_title)
        """
        # Remove @ if present
        if channel_input.startswith('@'):
            channel_input = channel_input[1:]
        
        # Handle different URL formats
        if channel_input.startswith('http'):
            parsed = urlparse(channel_input)
            if 't.me' in parsed.netloc:
                path_parts = parsed.path.strip('/').split('/')
                if len(path_parts) >= 1:
                    channel_username = path_parts[0]
                    topic_id = int(path_parts[1]) if len(path_parts) > 1 and path_parts[1].isdigit() else None
                    channel_link = f"https://t.me/{channel_username}"
                    return channel_username, topic_id, channel_link, None, None
        elif channel_input.startswith('t.me/'):
            path_parts = channel_input[5:].split('/')
            if len(path_parts) >= 1:
                channel_username = path_parts[0]
                topic_id = int(path_parts[1]) if len(path_parts) > 1 and path_parts[1].isdigit() else None
                channel_link = f"https://t.me/{channel_username}"
                return channel_username, topic_id, channel_link, None, None
        else:
            # Assume it's a username
            channel_link = f"https://t.me/{channel_input}"
            return channel_input, None, channel_link, None, None
        
        return None, None, None, None, None

    async def create_channel(self, channel_data: MonitoredChannelCreate, created_by: int) -> Optional[str]:
        """Create a new monitored channel"""
        try:
            db = await self._get_db()

            # Parse channel input
            channel_username, topic_id, channel_link, channel_id, topic_title = self._parse_channel_input(channel_data.channel_input)

            if not channel_username:
                logger.error("Invalid channel input: %s", channel_data.channel_input)
                return None

            # Resolve channel info using Telegram API
            channel_info = await self._resolve_channel_info(channel_data.channel_input)
            if not channel_info:
                logger.error("Failed to resolve channel info for: %s", channel_data.channel_input)
                return None

            # Validate that we have channel_id
            if "channel_id" not in channel_info or channel_info["channel_id"] is None:
                logger.error("Channel info missing channel_id: %s", channel_info)
                return None

            channel_id_str = str(channel_info["channel_id"])
            logger.info("Resolved channel info: ID=%s, username=%s, title=%s",
                       channel_id_str, channel_info.get("channel_username"), channel_info.get("channel_title"))

            # Check if channel already exists by channel_id
            existing_channel = await db.monitored_channels.find_one({
                "channel_id": channel_id_str
            })

            if existing_channel:
                logger.warning("Channel with ID %s already exists (existing doc ID: %s)",
                              channel_id_str, str(existing_channel["_id"]))
                return str(existing_channel["_id"])

            # Additional check: also check by username if available
            if channel_info.get("channel_username"):
                username_check = await db.monitored_channels.find_one({
                    "channel_username": channel_info["channel_username"]
                })
                if username_check and str(username_check.get("channel_id", "")) != channel_id_str:
                    logger.warning("Channel with username %s already exists but with different ID (%s vs %s). This might be a different channel.",
                                  channel_info["channel_username"], username_check.get("channel_id"), channel_id_str)
                    # Don't return existing - create new one as it might be a different channel with same username

            # Create channel document
            channel_doc = {
                "channel_id": channel_id_str,
                "channel_username": channel_info.get("channel_username"),
                "channel_title": channel_info.get("channel_title"),
                "channel_link": channel_info.get("channel_link"),
                "topic_id": topic_id or channel_data.topic_id,
                "topic_title": topic_title,
                "is_active": True,
                "monitor_all_topics": channel_data.monitor_all_topics,
                "monitored_topics": [topic_id] if topic_id else [],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "created_by": created_by
            }

            result = await db.monitored_channels.insert_one(channel_doc)
            new_channel_id = str(result.inserted_id)

            logger.info("Created new monitored channel: DB_ID=%s, Channel_ID=%s, Title=%s",
                       new_channel_id, channel_id_str, channel_info.get("channel_title"))
            return new_channel_id

        except Exception as e:
            logger.error("Error creating monitored channel: %s", e)
            return None

    async def get_all_channels(self) -> List[MonitoredChannelResponse]:
        """Get all monitored channels"""
        try:
            db = await self._get_db()
            channels = []
            async for doc in db.monitored_channels.find({}):
                channels.append(MonitoredChannelResponse.from_db_doc(doc))
            
            return channels
            
        except Exception as e:
            logger.error("Error getting all channels: %s", e)
            return []

    async def get_active_channels(self) -> List[MonitoredChannelResponse]:
        """Get all active monitored channels"""
        try:
            db = await self._get_db()
            channels = []
            async for doc in db.monitored_channels.find({"is_active": True}):
                channels.append(MonitoredChannelResponse.from_db_doc(doc))
            
            return channels
            
        except Exception as e:
            logger.error("Error getting active channels: %s", e)
            return []

    async def get_channel_by_id(self, channel_id: str) -> Optional[MonitoredChannelResponse]:
        """Get channel by ID"""
        try:
            db = await self._get_db()
            doc = await db.monitored_channels.find_one({"_id": ObjectId(channel_id)})
            if doc:
                return MonitoredChannelResponse.from_db_doc(doc)
            return None
            
        except Exception as e:
            logger.error("Error getting channel by ID: %s", e)
            return None

    async def update_channel(self, channel_id: str, update_data: dict) -> bool:
        """Update channel"""
        try:
            db = await self._get_db()
            update_data["updated_at"] = datetime.now(timezone.utc)
            
            result = await db.monitored_channels.update_one(
                {"_id": ObjectId(channel_id)},
                {"$set": update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error("Error updating channel: %s", e)
            return False

    async def delete_channel(self, channel_id: str) -> bool:
        """Delete channel"""
        try:
            db = await self._get_db()
            result = await db.monitored_channels.delete_one({"_id": ObjectId(channel_id)})
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error("Error deleting channel: %s", e)
            return False

    async def toggle_channel_status(self, channel_id: str) -> bool:
        """Toggle channel active status"""
        try:
            db = await self._get_db()
            channel = await db.monitored_channels.find_one({"_id": ObjectId(channel_id)})
            if not channel:
                return False
            
            new_status = not channel.get("is_active", True)
            result = await db.monitored_channels.update_one(
                {"_id": ObjectId(channel_id)},
                {"$set": {"is_active": new_status, "updated_at": datetime.now(timezone.utc)}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error("Error toggling channel status: %s", e)
            return False
