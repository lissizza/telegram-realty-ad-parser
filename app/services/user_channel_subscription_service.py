import logging
import re
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from bson import ObjectId
from telethon import TelegramClient

from app.core.config import settings
from app.db.mongodb import mongodb
from app.models.user_channel_subscription import (
    UserChannelSubscriptionCreate,
    UserChannelSubscriptionResponse,
)
from app.services.channel_resolver_service import ChannelResolverService

logger = logging.getLogger(__name__)


class UserChannelSubscriptionService:
    """Service for managing user channel subscriptions"""

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
            
            if not result:
                raise ValueError("Канал не найден. Проверьте правильность названия канала или ссылки.")
            
            return result
        except ValueError as ve:
            # Перебрасываем ValueError с понятным сообщением
            raise ve
        except Exception as e:
            logger.error("Error resolving channel info for '%s': %s", channel_input, e)
            # Проверяем тип ошибки для более понятного сообщения
            if "Nobody is using this username" in str(e) or "USERNAME_NOT_OCCUPIED" in str(e):
                raise ValueError("Канал не найден. Проверьте правильность названия канала или ссылки.")
            else:
                raise ValueError("Не удалось найти канал. Проверьте правильность данных.")
    
    async def _get_topic_title(self, channel_id: int, topic_id: int) -> Optional[str]:
        """Get topic title by channel ID and topic ID"""
        try:
            client = await self._get_telegram_client()
            if not client:
                logger.error("Cannot get topic title: Telegram client not available")
                return None
            
            resolver = ChannelResolverService(client)
            return await resolver.get_topic_title(channel_id, topic_id)
        except Exception as e:
            logger.error("Error getting topic title for channel %s, topic %s: %s", channel_id, topic_id, e)
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
        # Remove @ prefix if present and clean input
        channel_input = channel_input.strip().lstrip('@')
        
        logger.info("Parsing channel input: %s", channel_input)
        
        # Initialize return values
        channel_username = None
        topic_id = None
        channel_link = None
        channel_id = None
        topic_title = None
        
        # Pattern 1: Full Telegram URL with topic
        # Examples: https://t.me/rent_comissionfree/2629, t.me/channel/123
        tme_url_pattern = r'(?:https?://)?(?:www\.)?t\.me/([^/]+)(?:/(\d+))?'
        match = re.search(tme_url_pattern, channel_input)
        if match:
            channel_username = match.group(1)
            topic_id = int(match.group(2)) if match.group(2) else None
            channel_link = f"https://t.me/{channel_username}"
            if topic_id:
                channel_link += f"/{topic_id}"
            logger.info("Parsed from t.me URL: username=%s, topic_id=%s", channel_username, topic_id)
            return channel_username, topic_id, channel_link, channel_id, topic_title
        
        # Pattern 2: Direct channel ID (numeric)
        # Examples: -1001827102719, 1001827102719
        if re.match(r'^-?\d+$', channel_input):
            channel_id = int(channel_input)
            logger.info("Parsed as channel ID: %s", channel_id)
            # We don't have username yet, will need to resolve it later
            return channel_username, topic_id, channel_link, channel_id, topic_title
        
        # Pattern 3: Channel ID with topic (special format) - check this BEFORE username
        # Examples: -1001827102719:2629, 1001827102719:2629
        channel_topic_pattern = r'^(-?\d+)(?::(\d+))?$'
        match = re.match(channel_topic_pattern, channel_input)
        if match:
            channel_id = int(match.group(1))
            topic_id = int(match.group(2)) if match.group(2) else None
            logger.info("Parsed as channel_id:topic_id: %s:%s", channel_id, topic_id)
            return channel_username, topic_id, channel_link, channel_id, topic_title
        
        # Pattern 4: Username without protocol
        # Examples: rent_comissionfree, @channel_name
        if not channel_input.startswith('http') and '/' not in channel_input:
            channel_username = channel_input
            channel_link = f"https://t.me/{channel_username}"
            logger.info("Parsed as username: %s", channel_username)
            return channel_username, topic_id, channel_link, channel_id, topic_title
        
        # Pattern 5: Generic URL (fallback)
        # Try to extract from any URL
        parsed = urlparse(channel_input)
        if 't.me' in parsed.netloc:
            path_parts = parsed.path.strip('/').split('/')
            if path_parts and path_parts[0]:
                channel_username = path_parts[0]
                if len(path_parts) > 1 and path_parts[1].isdigit():
                    topic_id = int(path_parts[1])
                channel_link = f"https://t.me/{channel_username}"
                if topic_id:
                    channel_link += f"/{topic_id}"
                logger.info("Parsed from generic URL: username=%s, topic_id=%s", channel_username, topic_id)
                return channel_username, topic_id, channel_link, channel_id, topic_title
        
        # Default case - treat as username
        channel_username = channel_input
        channel_link = f"https://t.me/{channel_username}"
        logger.info("Default parsing as username: %s", channel_username)
        return channel_username, topic_id, channel_link, channel_id, topic_title

    async def create_subscription(self, subscription_data: UserChannelSubscriptionCreate) -> Optional[str]:
        """Create a new user channel subscription"""
        try:
            logger.info("Creating subscription for user %s, input: %s", 
                       subscription_data.user_id, subscription_data.channel_input)
            
            # Resolve channel information using Telegram API
            channel_info = await self._resolve_channel_info(subscription_data.channel_input)
            if not channel_info:
                logger.error("Could not resolve channel info from input: %s", subscription_data.channel_input)
                return None
            
            # Use provided topic_id or resolved one
            final_topic_id = subscription_data.topic_id or channel_info.get('topic_id')
            
            # Extract resolved information
            channel_id = channel_info['channel_id']
            channel_username = channel_info['channel_username']
            channel_title = channel_info['channel_title']
            channel_link = channel_info['channel_link']
            
            # Get topic title if topic_id is present
            topic_title = None
            if final_topic_id:
                topic_title = await self._get_topic_title(channel_id, final_topic_id)
            
            # Check if subscription already exists
            db = await self._get_db()
            query = {
                "user_id": subscription_data.user_id,
                "channel_id": str(channel_id)
            }
            
            if final_topic_id:
                query["topic_id"] = final_topic_id
            
            existing = await db.user_channel_subscriptions.find_one(query)
            
            if existing:
                logger.warning("Subscription already exists for user %s, query: %s", 
                             subscription_data.user_id, query)
                raise ValueError(f"У вас уже есть подписка на канал {channel_title}")
            
            # Create subscription document
            subscription_doc = {
                "user_id": subscription_data.user_id,
                "channel_id": str(channel_id),  # Store as string for consistency
                "channel_username": channel_username,
                "channel_title": channel_title,
                "channel_link": channel_link,
                "topic_id": final_topic_id,
                "topic_title": topic_title,
                "is_active": True,
                "monitor_all_topics": subscription_data.monitor_all_topics,
                "monitored_topics": subscription_data.monitored_topics,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            logger.info("Inserting subscription document: %s", subscription_doc)
            result = await db.user_channel_subscriptions.insert_one(subscription_doc)
            logger.info("Created subscription for user %s, channel_id=%s, channel_username=%s, id: %s", 
                       subscription_data.user_id, channel_id, channel_username, result.inserted_id)
            
            # Update topic cache if topic_id is present
            if final_topic_id:
                try:
                    from app.services import get_telegram_service
                    telegram_service = get_telegram_service()
                    if telegram_service:
                        await telegram_service.update_topic_cache(channel_id, final_topic_id)
                        logger.info("Updated topic cache for channel %s, topic %s", channel_id, final_topic_id)
                except Exception as e:
                    logger.warning("Failed to update topic cache: %s", e)
            
            return str(result.inserted_id)
            
        except ValueError as ve:
            # Re-raise ValueError so it can be caught by the API endpoint
            raise ve
        except Exception as e:
            logger.error("Error creating subscription: %s", e, exc_info=True)
            return None

    async def get_user_subscriptions(self, user_id: int) -> List[UserChannelSubscriptionResponse]:
        """Get all subscriptions for a user"""
        try:
            db = await self._get_db()
            subscriptions = []
            async for doc in db.user_channel_subscriptions.find({"user_id": user_id}):
                subscriptions.append(UserChannelSubscriptionResponse.from_db_doc(doc))
            
            return subscriptions
            
        except Exception as e:
            logger.error("Error getting user subscriptions: %s", e)
            return []

    async def get_active_user_subscriptions(self, user_id: int) -> List[UserChannelSubscriptionResponse]:
        """Get active subscriptions for a user"""
        try:
            db = await self._get_db()
            subscriptions = []
            async for doc in db.user_channel_subscriptions.find({
                "user_id": user_id,
                "is_active": True
            }):
                subscriptions.append(UserChannelSubscriptionResponse.from_db_doc(doc))
            
            return subscriptions
            
        except Exception as e:
            logger.error("Error getting active user subscriptions: %s", e)
            return []

    async def update_subscription(self, subscription_id: str, updates: dict) -> bool:
        """Update a subscription"""
        try:
            if not ObjectId.is_valid(subscription_id):
                return False
            
            db = await self._get_db()
            updates["updated_at"] = datetime.utcnow()
            
            result = await db.user_channel_subscriptions.update_one(
                {"_id": ObjectId(subscription_id)},
                {"$set": updates}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error("Error updating subscription: %s", e)
            return False

    async def delete_subscription(self, subscription_id: str) -> bool:
        """Delete a subscription"""
        try:
            if not ObjectId.is_valid(subscription_id):
                return False
            
            db = await self._get_db()
            result = await db.user_channel_subscriptions.delete_one({
                "_id": ObjectId(subscription_id)
            })
            
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error("Error deleting subscription: %s", e)
            return False

    async def toggle_subscription_active(self, subscription_id: str) -> bool:
        """Toggle subscription active status"""
        try:
            if not ObjectId.is_valid(subscription_id):
                return False
            
            db = await self._get_db()
            # Get current status
            subscription = await db.user_channel_subscriptions.find_one({
                "_id": ObjectId(subscription_id)
            })
            
            if not subscription:
                return False
            
            # Toggle status
            new_status = not subscription.get("is_active", True)
            
            result = await db.user_channel_subscriptions.update_one(
                {"_id": ObjectId(subscription_id)},
                {"$set": {"is_active": new_status, "updated_at": datetime.utcnow()}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error("Error toggling subscription status: %s", e)
            return False

    async def get_all_active_subscriptions(self) -> List[UserChannelSubscriptionResponse]:
        """Get all active subscriptions (for monitoring)"""
        try:
            db = await self._get_db()
            subscriptions = []
            logger.info("Starting to fetch all active subscriptions")
            
            async for doc in db.user_channel_subscriptions.find({"is_active": True}):
                doc["id"] = str(doc["_id"])
                logger.info("Processing subscription doc: %s", doc)
                
                try:
                    # Use from_db_doc method for proper deserialization
                    subscription = UserChannelSubscriptionResponse.from_db_doc(doc)
                    subscriptions.append(subscription)
                    logger.info("Successfully created subscription response")
                except Exception as validation_error:
                    logger.error("Validation error for doc %s: %s", doc, validation_error)
                    # Try to create with raw data for debugging
                    try:
                        raw_subscription = UserChannelSubscriptionResponse(**doc)
                        subscriptions.append(raw_subscription)
                        logger.info("Successfully created raw subscription response")
                    except Exception as raw_error:
                        logger.error("Raw creation also failed: %s", raw_error)
            
            logger.info("Returning %s subscriptions", len(subscriptions))
            return subscriptions
            
        except Exception as e:
            logger.error("Error getting all active subscriptions: %s", e, exc_info=True)
            return []

