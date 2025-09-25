"""
Service for resolving channel information from various input formats
"""
import logging
import re
from typing import Dict, Optional, Tuple, Union
from urllib.parse import urlparse

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChannelResolverService:
    """Service for resolving channel information from user input"""

    def __init__(self, client: TelegramClient):
        self.client = client

    async def resolve_channel_info(self, user_input: str) -> Optional[Dict[str, Union[str, int]]]:
        """
        Resolve complete channel information from user input
        
        Args:
            user_input: Channel input in various formats:
                - @channel_username
                - channel_username
                - https://t.me/channel_username
                - https://t.me/channel_username/topic_id
                - https://t.me/c/channel_id
                - https://t.me/c/channel_id/message_id
                - -1001827102719 (channel ID)
                - -1001827102719:2629 (channel ID with topic)
        
        Returns:
            Dict with channel information:
            {
                'channel_id': int,
                'channel_username': str,
                'channel_title': str,
                'topic_id': Optional[int],
                'channel_link': str
            }
        """
        try:
            # Clean input
            user_input = user_input.strip()
            
            # Parse different input formats
            if user_input.startswith("https://t.me/"):
                return await self._resolve_from_url(user_input)
            elif user_input.startswith("@"):
                return await self._resolve_from_username(user_input[1:])
            elif ":" in user_input and user_input.startswith("-"):
                # Channel ID with topic: -1001827102719:2629
                return await self._resolve_from_channel_id_with_topic(user_input)
            elif user_input.startswith("-"):
                # Channel ID: -1001827102719
                return await self._resolve_from_channel_id(user_input)
            else:
                # Username without @
                return await self._resolve_from_username(user_input)
                
        except Exception as e:
            logger.error("Error resolving channel info for input '%s': %s", user_input, e)
            return None

    async def _resolve_from_url(self, url: str) -> Optional[Dict[str, Union[str, int]]]:
        """Resolve channel info from Telegram URL"""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")
            
            if path.startswith("c/"):
                # https://t.me/c/channel_id/message_id
                parts = path.split("/")
                if len(parts) >= 2:
                    channel_id = int(parts[1])
                    # Convert to negative ID for supergroups
                    if channel_id > 0:
                        channel_id = -(channel_id + 1000000000000)
                    return await self._get_channel_info_by_id(channel_id)
            else:
                # https://t.me/channel_username or https://t.me/channel_username/topic_id
                parts = path.split("/")
                username = parts[0]
                topic_id = int(parts[1]) if len(parts) > 1 else None
                
                channel_info = await self._get_channel_info_by_username(username)
                if channel_info and topic_id:
                    channel_info['topic_id'] = topic_id
                return channel_info
                
        except Exception as e:
            logger.error("Error parsing URL '%s': %s", url, e)
            return None

    async def _resolve_from_username(self, username: str) -> Optional[Dict[str, Union[str, int]]]:
        """Resolve channel info from username"""
        return await self._get_channel_info_by_username(username)

    async def _resolve_from_channel_id(self, channel_id_str: str) -> Optional[Dict[str, Union[str, int]]]:
        """Resolve channel info from channel ID"""
        try:
            channel_id = int(channel_id_str)
            return await self._get_channel_info_by_id(channel_id)
        except ValueError:
            logger.error("Invalid channel ID format: %s", channel_id_str)
            return None

    async def _resolve_from_channel_id_with_topic(self, input_str: str) -> Optional[Dict[str, Union[str, int]]]:
        """Resolve channel info from channel ID with topic"""
        try:
            channel_id_str, topic_id_str = input_str.split(":", 1)
            channel_id = int(channel_id_str)
            topic_id = int(topic_id_str)
            
            channel_info = await self._get_channel_info_by_id(channel_id)
            if channel_info:
                channel_info['topic_id'] = topic_id
            return channel_info
        except ValueError:
            logger.error("Invalid channel ID with topic format: %s", input_str)
            return None

    async def _get_channel_info_by_username(self, username: str) -> Optional[Dict[str, Union[str, int]]]:
        """Get channel info by username"""
        try:
            entity = await self.client.get_entity(username)
            return await self._extract_channel_info(entity)
        except Exception as e:
            logger.error("Error getting channel info by username '%s': %s", username, e)
            return None

    async def _get_channel_info_by_id(self, channel_id: int) -> Optional[Dict[str, Union[str, int]]]:
        """Get channel info by channel ID"""
        try:
            entity = await self.client.get_entity(channel_id)
            return await self._extract_channel_info(entity)
        except Exception as e:
            logger.error("Error getting channel info by ID %s: %s", channel_id, e)
            return None

    async def _extract_channel_info(self, entity) -> Optional[Dict[str, Union[str, int]]]:
        """Extract channel information from Telegram entity"""
        try:
            if isinstance(entity, (Channel, Chat)):
                # Get channel ID
                channel_id = entity.id
                
                # Get username
                username = getattr(entity, 'username', None)
                if username:
                    username = f"@{username}"
                
                # Get title
                title = getattr(entity, 'title', 'Unknown Channel')
                
                # Generate channel link
                if username:
                    channel_link = f"https://t.me/{username.replace('@', '')}"
                else:
                    # For channels without username, use c/ format
                    if channel_id < 0:
                        # Convert negative ID to positive for c/ format
                        positive_id = abs(channel_id) - 1000000000000
                        channel_link = f"https://t.me/c/{positive_id}"
                    else:
                        channel_link = f"https://t.me/c/{channel_id}"
                
                return {
                    'channel_id': channel_id,
                    'channel_username': username or str(channel_id),
                    'channel_title': title,
                    'topic_id': None,
                    'channel_link': channel_link
                }
            else:
                logger.error("Entity is not a channel or chat: %s", type(entity))
                return None
                
        except Exception as e:
            logger.error("Error extracting channel info from entity: %s", e)
            return None

    async def get_topic_title(self, channel_id: int, topic_id: int) -> Optional[str]:
        """
        Get topic title by channel ID and topic ID
        
        Args:
            channel_id: Channel ID
            topic_id: Topic ID
            
        Returns:
            Topic title or None if not found
        """
        try:
            # Get channel entity
            channel = await self.client.get_entity(channel_id)
            
            if not isinstance(channel, Channel):
                logger.warning("Entity %s is not a channel", channel_id)
                return None
            
            # Check if channel has topics (is a supergroup with topics enabled)
            if not getattr(channel, 'forum', False):
                logger.warning("Channel %s does not have topics enabled", channel_id)
                return None
            
            # Get channel full info to access topics
            full_channel = await self.client.get_entity(channel)
            
            # Try to get topic info
            try:
                # This is a simplified approach - in practice, getting topic titles
                # requires more complex API calls that might not be available in all cases
                logger.info("Attempting to get topic title for channel %s, topic %s", channel_id, topic_id)
                
                # For now, return a generic title based on topic ID
                # In a real implementation, you would need to use specific Telegram API methods
                # to get the actual topic titles
                return f"Topic {topic_id}"
                
            except Exception as e:
                logger.warning("Could not get topic title for %s:%s: %s", channel_id, topic_id, e)
                return f"Topic {topic_id}"
                
        except Exception as e:
            logger.error("Error getting topic title for channel %s, topic %s: %s", channel_id, topic_id, e)
            return None

    def validate_channel_input(self, user_input: str) -> bool:
        """
        Validate if user input looks like a valid channel identifier
        
        Args:
            user_input: User input to validate
            
        Returns:
            True if input looks valid, False otherwise
        """
        if not user_input or not user_input.strip():
            return False
            
        user_input = user_input.strip()
        
        # Check for various valid formats
        patterns = [
            r'^@[a-zA-Z0-9_]+$',  # @username
            r'^[a-zA-Z0-9_]+$',   # username
            r'^https://t\.me/[a-zA-Z0-9_]+/?.*$',  # https://t.me/username
            r'^https://t\.me/c/\d+/?.*$',  # https://t.me/c/channel_id
            r'^-\d+$',  # -1001827102719
            r'^-\d+:\d+$',  # -1001827102719:2629
        ]
        
        for pattern in patterns:
            if re.match(pattern, user_input):
                return True
                
        return False
