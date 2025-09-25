import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telethon import TelegramClient, events
from telethon.tl.types import Message

from app.core.config import settings
from app.db.mongodb import mongodb
from app.models.incoming_message import IncomingMessage
from app.models.simple_filter import SimpleFilter
from app.models.telegram import RealEstateAd
from app.services.llm_service import LLMService
from app.services.notification_service import TelegramNotificationService
from app.services.simple_filter_service import SimpleFilterService
from app.services.user_service import user_service

logger = logging.getLogger(__name__)


class TelegramService:
    """Service for monitoring Telegram channels and processing real estate ads"""

    def __init__(self) -> None:
        self.client: Optional[TelegramClient] = None
        self.llm_service = LLMService()
        self.simple_filter_service = SimpleFilterService()
        self.notification_service: Optional[TelegramNotificationService] = None
        self.is_monitoring = False
        # Cache for topic top_message IDs to reduce API calls
        self.topic_cache: Dict[tuple[int, int], int] = {}  # (channel_id, topic_id) -> top_message_id

    def set_notification_service(self, bot: Any) -> None:
        """Set the notification service with bot instance"""
        self.notification_service = TelegramNotificationService(bot)

    async def _initialize_topic_cache(self) -> None:
        """Initialize topic cache with top_message IDs for common topics"""
        if not self.client:
            logger.warning("Telegram client not available for topic cache initialization")
            return

        try:
            # Get all active subscriptions to find unique channel-topic combinations
            db = mongodb.get_database()
            subscriptions = await db.user_channel_subscriptions.find({
                "is_active": True,
                "topic_id": {"$ne": None}
            }).to_list(length=None)

            # Extract unique channel-topic combinations
            unique_combinations = set()
            for sub in subscriptions:
                channel_id = sub.get("channel_id")
                topic_id = sub.get("topic_id")
                if channel_id and topic_id:
                    # Convert channel_id to integer if it's a string
                    if isinstance(channel_id, str):
                        try:
                            channel_id = int(channel_id)
                        except ValueError:
                            continue
                    unique_combinations.add((channel_id, topic_id))

            logger.info("Initializing topic cache for %d unique channel-topic combinations", len(unique_combinations))

            # Cache top_message for each combination
            for channel_id, topic_id in unique_combinations:
                try:
                    top_message = await self._get_top_message_for_topic(channel_id, topic_id)
                    if top_message:
                        self.topic_cache[(channel_id, topic_id)] = top_message
                        logger.info("Cached top_message %s for channel %s, topic %s", top_message, channel_id, topic_id)
                    else:
                        logger.warning("Could not get top_message for channel %s, topic %s", channel_id, topic_id)
                except Exception as e:
                    logger.error("Error caching topic %s in channel %s: %s", topic_id, channel_id, e)

            logger.info("Topic cache initialized with %d entries", len(self.topic_cache))

        except Exception as e:
            logger.error("Error initializing topic cache: %s", e)

    async def _update_topic_cache(self, channel_id: int, topic_id: int) -> None:
        """Update topic cache with a new channel-topic combination"""
        if not self.client:
            logger.warning("Telegram client not available for topic cache update")
            return

        try:
            # Convert channel_id to integer if it's a string
            if isinstance(channel_id, str):
                try:
                    channel_id = int(channel_id)
                except ValueError:
                    logger.error("Invalid channel_id format: %s", channel_id)
                    return

            cache_key = (channel_id, topic_id)
            
            # Skip if already cached
            if cache_key in self.topic_cache:
                logger.debug("Topic %s in channel %s already cached", topic_id, channel_id)
                return

            # Get top_message and cache it
            top_message = await self._get_top_message_for_topic(channel_id, topic_id)
            if top_message:
                self.topic_cache[cache_key] = top_message
                logger.info("Updated topic cache with top_message %s for channel %s, topic %s", 
                          top_message, channel_id, topic_id)
            else:
                logger.warning("Could not get top_message for channel %s, topic %s", channel_id, topic_id)

        except Exception as e:
            logger.error("Error updating topic cache for channel %s, topic %s: %s", channel_id, topic_id, e)

    async def update_topic_cache(self, channel_id: int, topic_id: int) -> None:
        """Public method to update topic cache when new subscriptions are added"""
        await self._update_topic_cache(channel_id, topic_id)

    async def start_monitoring(self) -> None:
        """Start monitoring Telegram channels"""
        if self.is_monitoring:
            logger.warning("Monitoring is already active")
            return

        try:
            # Initialize Telegram client
            self.client = TelegramClient(
                settings.TELEGRAM_SESSION_NAME, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH
            )

            await self.client.start(phone=settings.TELEGRAM_PHONE)

            # Initialize topic cache for better performance
            await self._initialize_topic_cache()

            # Get monitored channels from user subscriptions
            user_channels = await self._get_user_monitored_channels()
            
            # Fallback to legacy channels if no user subscriptions
            if not user_channels:
                monitored_channels = self._get_monitored_channels()
                if monitored_channels:
                    logger.info("Using legacy monitored channels: %s", monitored_channels)
                    
                    @self.client.on(events.NewMessage(chats=monitored_channels))
                    async def handle_new_message_legacy(event: events.NewMessage.Event) -> None:
                        # Process only messages from main topic (reply_to_msg_id=2629)
                        # Skip all other subchannels
                        message = event.message
                        rt = getattr(message, "reply_to", None)
                        reply_to_msg_id = getattr(rt, "reply_to_msg_id", None) if rt else None

                        logger.info("Message %s: reply_to=%s, reply_to_msg_id=%s", message.id, rt, reply_to_msg_id)

                        if rt and reply_to_msg_id == 2629:
                            # Message from main topic with real estate ads, process it
                            logger.info("Message %s from main topic (reply_to_msg_id=2629), processing", message.id)
                        else:
                            # Message from other subchannels or no reply_to, skip it
                            logger.info(
                                "Message %s from subchannel %s or no reply_to, skipping", message.id, reply_to_msg_id
                            )
                            return
                        await self._process_message(event.message, user_id=None)
            else:
                # Use user subscriptions for monitoring
                channel_ids = list(user_channels.keys())
                logger.info("Using user monitored channels: %s", channel_ids)
                
                @self.client.on(events.NewMessage(chats=channel_ids))
                async def handle_new_message_user(event: events.NewMessage.Event) -> None:
                    await self._handle_user_subscription_message(event, user_channels)

            self.is_monitoring = True
            logger.info("Started monitoring Telegram channels")

            # Keep the client running
            await self.client.run_until_disconnected()

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error starting monitoring: %s", e)
            raise

    async def _handle_user_subscription_message(self, event: events.NewMessage.Event, user_channels: Dict[int, List[Dict]]) -> None:
        """Handle new message from user subscribed channels using top_message filtering"""
        try:
            message = event.message
            chat_id = event.chat_id
            
            logger.info("Processing message %s from channel %s", message.id, chat_id)
            
            # Get subscriptions for this channel
            channel_subscriptions = user_channels.get(chat_id, [])
            if not channel_subscriptions:
                logger.warning("No subscriptions found for channel %s", chat_id)
                return
            
            # Process message for each matching subscription
            for subscription in channel_subscriptions:
                user_id = subscription["user_id"]
                topic_id = subscription["topic_id"]
                monitor_all_topics = subscription["monitor_all_topics"]
                monitored_topics = subscription["monitored_topics"]
                
                # Check if message matches subscription criteria using top_message approach
                should_process = False
                
                if monitor_all_topics:
                    # Monitor all topics in this channel - process all messages
                    should_process = True
                    logger.info("Processing message for user %s (monitor_all_topics=True)", user_id)
                elif topic_id:
                    # Monitor specific topic - check if message belongs to this topic
                    should_process = await self._is_message_in_topic(message, chat_id, topic_id)
                    if should_process:
                        logger.info("Processing message for user %s (topic_id=%s)", user_id, topic_id)
                elif monitored_topics:
                    # Monitor specific topics from list - check if message belongs to any of them
                    for t_id in monitored_topics:
                        if await self._is_message_in_topic(message, chat_id, t_id):
                            should_process = True
                            logger.info("Processing message for user %s (monitored_topics=%s, matched=%s)", user_id, monitored_topics, t_id)
                            break
                else:
                    # Monitor main channel (no topic filtering) - process all messages
                    should_process = True
                    logger.info("Processing message for user %s (main channel)", user_id)
                
                if should_process:
                    # Process message for this user
                    await self._process_message_for_user(message, user_id, subscription)
                else:
                    logger.info("Skipping message for user %s (doesn't match criteria)", user_id)
                    
        except Exception as e:
            logger.error("Error handling user subscription message: %s", e)

    async def _process_message_for_user(self, message, user_id: int, subscription: Dict) -> None:
        """Process message for a specific user"""
        try:
            # Use existing _process_message logic
            # The _process_message method already handles LLM parsing and filter checking
            # It will create UserFilterMatch records for matching filters automatically
            await self._process_message(message, force=False, user_id=user_id)
            logger.info("Message %s processed for user %s", message.id, user_id)
                
        except Exception as e:
            logger.error("Error processing message for user %s: %s", user_id, e)

    async def stop_monitoring(self) -> None:
        """Stop monitoring Telegram channels"""
        if not self.is_monitoring:
            logger.warning("Monitoring is not active")
            return

        try:
            if self.client:
                await self.client.disconnect()
            self.is_monitoring = False
            logger.info("Stopped monitoring Telegram channels")
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error stopping monitoring: %s", e)
            raise

    async def analyze_channel_structure(self, channel_id: int, limit: int = 50) -> Optional[Dict[str, Any]]:
        """Analyze channel structure to understand topics"""
        logger.info("Analyzing channel structure for channel %s", channel_id)
        topic_stats: Dict[int, int] = {}
        no_topic_count = 0
        sample_messages: List[Dict[str, Any]] = []

        try:
            if not self.client:
                logger.error("Telegram client not initialized")
                return None
            async for message in self.client.iter_messages(channel_id, limit=limit):
                if message.reply_to and hasattr(message.reply_to, "reply_to_top_id"):
                    topic_id = message.reply_to.reply_to_top_id
                    if topic_id not in topic_stats:
                        topic_stats[topic_id] = 0
                    topic_stats[topic_id] += 1
                else:
                    no_topic_count += 1

                # Collect sample messages for analysis
                if len(sample_messages) < 10:
                    sample_messages.append(
                        {
                            "id": message.id,
                            "text": message.text[:100] if message.text else "No text",
                            "reply_to": message.reply_to,
                            "reply_to_top_id": (
                                getattr(message.reply_to, "reply_to_top_id", None) if message.reply_to else None
                            ),
                            "date": message.date,
                        }
                    )

            # Log results
            logger.info("Channel %s analysis results:", channel_id)
            logger.info("Messages without topic (main channel): %s", no_topic_count)
            logger.info("Topics and message counts:")
            for topic_id, count in topic_stats.items():
                logger.info("  Topic %s: %s messages", topic_id, count)

            logger.info("Sample messages:")
            for msg in sample_messages:
                logger.info("  Message ID: %s", msg["id"])
                logger.info("  Text: %s...", msg["text"])
                logger.info("  Reply to: %s", msg["reply_to"])
                logger.info("  Reply to top ID: %s", msg["reply_to_top_id"])
                logger.info("  Date: %s", msg["date"])
                logger.info("-" * 50)

            return {
                "channel_id": channel_id,
                "no_topic_count": no_topic_count,
                "topic_stats": topic_stats,
                "sample_messages": sample_messages,
            }

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error analyzing channel structure: %s", e)
            return None

    async def get_status(self) -> Dict[str, Any]:
        """Get bot status"""
        return {
            "is_monitoring": self.is_monitoring,
            "is_connected": (self.client and self.client.is_connected() if self.client else False),
        }

    def _get_monitored_channels(self) -> List[int]:
        """Get list of monitored channel IDs from settings"""
        try:
            # Get channels from settings
            channel_strings = settings.monitored_channels_list

            if not channel_strings:
                logger.warning("No monitored channels configured")
                return []

            # Convert string IDs to integers
            channel_ids: List[Any] = []
            for channel_id in channel_strings:
                channel_id = channel_id.strip()
                if not channel_id:
                    continue
                try:
                    # Handle both @username and numeric IDs
                    if channel_id.startswith("@"):
                        # For @username, we need to resolve it to numeric ID
                        # This will be handled by Telethon automatically
                        channel_ids.append(channel_id)
                    else:
                        # Convert numeric string to int
                        channel_ids.append(int(channel_id))
                except ValueError as e:
                    logger.warning("Invalid channel ID format: %s - %s", channel_id, e)
                    continue

            if not channel_ids:
                logger.warning("No valid monitored channels found")
                return []

            logger.info("Monitoring %s channels (legacy): %s", len(channel_ids), channel_ids)
            return channel_ids
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error getting monitored channels: %s", e)
            return []

    async def _get_user_monitored_channels(self) -> Dict[int, List[Dict]]:
        """Get monitored channels from user subscriptions"""
        try:
            from app.services.user_channel_subscription_service import (
                UserChannelSubscriptionService,
            )
            
            subscription_service = UserChannelSubscriptionService()
            subscriptions = await subscription_service.get_all_active_subscriptions()
            logger.info("Found %d active subscriptions", len(subscriptions))
            
            # Group subscriptions by channel
            channels = {}
            for subscription in subscriptions:
                channel_id = subscription.channel_id
                if not channel_id:
                    # Skip subscriptions without channel_id
                    logger.warning("Subscription %s has no channel_id", subscription.id)
                    continue
                
                # Convert channel_id to integer for Telethon
                try:
                    if isinstance(channel_id, str):
                        if channel_id.startswith("-"):
                            # Negative channel ID
                            channel_id_int = int(channel_id)
                        elif channel_id.startswith("@"):
                            # Username, skip for now
                            logger.warning("Username channel %s not supported yet", channel_id)
                            continue
                        else:
                            # Try to parse as integer and convert to supergroup format
                            channel_id_int = int(channel_id)
                            # Convert to supergroup format (-100XXXXXXXXXX)
                            if channel_id_int > 0:
                                channel_id_int = -(channel_id_int + 1000000000000)
                    else:
                        channel_id_int = int(channel_id)
                except (ValueError, TypeError):
                    logger.warning("Invalid channel_id format: %s", channel_id)
                    continue
                
                if channel_id_int not in channels:
                    channels[channel_id_int] = []
                
                channels[channel_id_int].append({
                    "user_id": subscription.user_id,
                    "topic_id": subscription.topic_id,
                    "monitor_all_topics": subscription.monitor_all_topics,
                    "monitored_topics": subscription.monitored_topics,
                    "subscription_id": subscription.id
                })
            
            logger.info("User monitored channels: %s", list(channels.keys()))
            return channels
            
        except Exception as e:
            logger.error("Error getting user monitored channels: %s", e)
            return {}

    def _get_monitored_subchannels(self) -> List[tuple]:
        """Get list of monitored subchannel (topic) IDs from settings"""
        try:
            subchannels = settings.monitored_subchannels_list

            if not subchannels:
                logger.info("No monitored subchannels configured")
                return []

            logger.info("Monitoring %s subchannels: %s", len(subchannels), subchannels)
            return subchannels
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error getting monitored subchannels: %s", e)
            return []


    def _is_message_in_topic_correct(self, message: Message) -> bool:
        """Check if message is in the main topic (no reply_to) - where real estate ads are posted"""
        try:
            # We want messages from the main topic (no reply_to)
            # Real estate ads are posted in the main topic, not in sub-topics
            rt = getattr(message, "reply_to", None)
            if rt:
                reply_to_top_id = getattr(rt, "reply_to_top_id", None)
                logger.debug("Message %s: reply_to_top_id=%s (sub-topic, skipping)", message.id, reply_to_top_id)
                return False
            else:
                logger.debug("Message %s: no reply_to (main topic, processing)", message.id)
                return True

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error checking topic: %s", e)
            return False

    def _is_from_monitored_subchannel(self, message: Message) -> bool:
        """Check if message is from a monitored subchannel (topic)"""
        try:
            # For user subscription monitoring, we should process all messages
            # The filtering by channel and topic is already done in _handle_user_subscription_message
            # If there's a topic_id in the subscription, it will be checked there
            logger.debug("Message %s from channel %s, processing (user subscription mode)", message.id, message.chat_id)
            return True
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error checking subchannel: %s", e)
            return False

    def _is_technical_bot_message(self, message_text: str) -> bool:
        """Check if message is a technical bot message that should be skipped"""
        if not message_text:
            return False

        tech_indicators = [
            "недостаточно прав",
            "блокировки",
            "тихий режим",
            "настройки бота",
            "технические особенности",
            "работать некорректно",
            "cas.chat",
        ]

        return any(tech_indicator in message_text.lower() for tech_indicator in tech_indicators)

    def _is_media_only_message(self, message: Message) -> bool:
        """Check if message contains only media without text"""
        try:
            # Check if message has text
            if message.text and message.text.strip():
                return False

            # Check if message has media
            has_media = (
                message.photo
                or message.video
                or message.document
                or message.audio
                or message.voice
                or message.video_note
                or message.sticker
                or message.animation
                or message.contact
                or message.location
                or message.venue
                or message.poll
                or message.game
                or message.web_preview
            )

            return bool(has_media)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error checking media-only message: %s", e)
            return False

    async def _save_message_status(self, message: Message, status: str) -> None:
        """Save message with specific status using IncomingMessage model"""
        try:
            db = mongodb.get_database()
            message_text = message.text or ""

            # Get channel title
            channel_title = "Unknown Channel"
            try:
                if self.client:
                    channel = await self.client.get_entity(message.chat_id)
                    channel_title = getattr(channel, "title", "Unknown Channel")
            except Exception:  # pylint: disable=broad-except
                pass

            # Get topic_id for this channel from settings
            topic_id = settings.get_topic_id_for_channel(message.chat_id)

            # Create IncomingMessage object
            incoming_message = IncomingMessage(
                id=message.id,
                channel_id=message.chat_id,
                topic_id=topic_id,
                channel_title=channel_title,
                message=message_text,
                date=message.date,
                processing_status=status,
                processed_at=datetime.utcnow() if status in ["completed", "failed"] else None,
                parsing_errors=[],
                is_spam=False,
                spam_reason=None,
                is_real_estate=False,
                real_estate_confidence=0.0,
                real_estate_ad_id=None,
                forwarded=False,
                forwarded_at=None,
                forwarded_to=None,
            )

            # Convert to dict for MongoDB
            message_data = incoming_message.model_dump(exclude={"id"})

            await db.incoming_messages.update_one(
                {"id": message.id, "channel_id": message.chat_id}, {"$set": message_data}, upsert=True
            )

            logger.info("Saved message %s with status %s", message.id, status)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error saving message status: %s", e)

    async def _process_message(self, message: Message, force: bool = False, user_id: Optional[int] = None) -> None:
        """Process incoming message"""
        real_estate_ad = None  # Initialize variable
        logger.info("DEBUG: _process_message called for message %s", message.id)
        logger.info("DEBUG: Message type: %s", type(message))
        logger.info("DEBUG: Message chat_id: %s", message.chat_id)
        logger.info("DEBUG: Message text: %s", message.text[:100] if message.text else "None")
        logger.info("DEBUG: About to enter try block")
        try:
            # Check if message is from monitored subchannel (topic)
            if not self._is_from_monitored_subchannel(message):
                logger.debug("Message %s not from monitored subchannel, skipping", message.id)
                return

            logger.debug("Message %s is from monitored subchannel, continuing", message.id)

            # Check if message is media-only (skip processing completely)
            if self._is_media_only_message(message):
                logger.debug("Message %s is media-only, skipping completely", message.id)
                return

            logger.debug("Message %s is not media-only, continuing", message.id)
            # Check if message already processed
            db = mongodb.get_database()
            existing_post = await db.incoming_messages.find_one({"id": message.id, "channel_id": message.chat_id})

            if existing_post:
                # Check if we need to reprocess (e.g., if status is ERROR or force=True)
                if not force and existing_post.get("processing_status") not in ["error"]:
                    logger.debug(
                        "Message %s already processed with status %s, skipping",
                        message.id,
                        existing_post.get("processing_status"),
                    )
                    return

                logger.info(
                    "Reprocessing message %s (previous status: %s)",
                    message.id,
                    existing_post.get("processing_status"),
                )

            # Create post data with initial status (IncomingMessage format)
            channel_title = "Unknown"
            try:
                if message.chat and hasattr(message.chat, "title"):
                    channel_title = message.chat.title
            except Exception as e:  # pylint: disable=broad-except
                logger.warning("Could not get channel title for message %s: %s", message.id, e)

            post_data = {
                "id": message.id,
                "channel_id": message.chat_id,
                "channel_title": channel_title,
                "message": message.text or "",
                "date": message.date,
                "views": getattr(message, "views", None),
                "forwards": getattr(message, "forwards", None),
                "replies": None,  # Skip replies object as it's not serializable
                "media_type": None,
                "media_url": None,
                "processing_status": "pending",
                "processed_at": None,
                "parsing_errors": [],
                "is_spam": None,
                "spam_reason": None,
                "is_real_estate": None,
                "real_estate_confidence": None,
                "real_estate_ad_id": None,
                "forwarded": False,
                "forwarded_at": None,
                "forwarded_to": None,
            }

            logger.debug("Created post_data for message %s", message.id)
            logger.debug("Message date type: %s", type(message.date))
            logger.debug("Message chat_id: %s", message.chat_id)
            logger.debug("Message text length: %s", len(message.text or ""))
            logger.debug("Channel title: %s", channel_title)

            # Save or update IncomingMessage first
            if existing_post:
                # Update existing post
                result = await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id}, {"$set": post_data}
                )
                logger.debug("Updated incoming_message for %s: %s modified", message.id, result.modified_count)
                incoming_message_id = str(existing_post["_id"])
            else:
                # Insert new post
                result = await db.incoming_messages.insert_one(post_data)
                logger.debug("Inserted incoming_message for %s: %s", message.id, result.inserted_id)
                incoming_message_id = str(result.inserted_id)

            # Try to parse as real estate ad using LLM
            message_text = message.text or ""
            logger.info("Message %s: text='%s', has_text=%s", message.id, message_text, bool(message.text))

            # Skip technical bot messages
            if self._is_technical_bot_message(message_text):
                logger.info("Message %s is a technical bot message, skipping", message.id)
                return

            if message_text:
                # Skip spam filtering - LLM will handle it

                # Let LLM determine if it's a real estate ad
                logger.info("Processing message %s with LLM", message.id)

                # Update status to parsing
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {"$set": {"processing_status": "processing", "updated_at": message.date}},
                )

                # Use parser service which will choose between LLM and rule-based parsing
                # Create IncomingMessage object for parsing
                # Get topic_id for this channel from settings
                topic_id = settings.get_topic_id_for_channel(message.chat_id)

                incoming_message_obj = IncomingMessage(
                    id=message.id,
                    channel_id=message.chat_id,
                    topic_id=topic_id,
                    channel_title=channel_title,
                    message=message_text,
                    date=message.date,
                    processing_status="processing",
                )
                # Set the MongoDB ID
                incoming_message_obj._id = incoming_message_id  # pylint: disable=protected-access

                real_estate_ad = await self.llm_service.parse_with_llm(
                    incoming_message_obj.message,
                    incoming_message_obj.id,
                    incoming_message_obj.channel_id,
                    incoming_message_id,
                    incoming_message_obj.topic_id,
                )

                if real_estate_ad:
                    # Check if LLM determined this is actually real estate
                    if real_estate_ad.is_real_estate:
                        # Check simple filters (exact field matching)
                        filter_result = await self.simple_filter_service.check_filters(real_estate_ad, user_id)

                        # Update ad with filter matching information
                        # Note: matched_filters is now handled via UserFilterMatch model
                        # Note: should_forward is now handled via UserFilterMatch model

                        # Save parsed ad with filter information
                        ad_data = real_estate_ad.dict(exclude={"id"})
                        result = await db.real_estate_ads.replace_one(
                            {"original_post_id": message.id}, ad_data, upsert=True
                        )
                        if result.upserted_id:
                            real_estate_ad.id = str(result.upserted_id)
                        else:
                            # Find existing record to get its ID
                            existing = await db.real_estate_ads.find_one({"original_post_id": message.id})
                            if existing:
                                real_estate_ad.id = str(existing["_id"])

                        # Update post status to parsed (only if it's actually real estate)
                        await db.incoming_messages.update_one(
                            {"id": message.id, "channel_id": message.chat_id},
                            {
                                "$set": {
                                    "processing_status": "parsed",
                                    "is_real_estate": True,
                                    "real_estate_confidence": real_estate_ad.parsing_confidence,
                                    "real_estate_ad_id": real_estate_ad.id,
                                    "updated_at": message.date,
                                }
                            },
                        )
                    else:
                        # LLM determined this is not real estate
                        await db.incoming_messages.update_one(
                            {"id": message.id, "channel_id": message.chat_id},
                            {
                                "$set": {
                                    "processing_status": "not_real_estate",
                                    "is_real_estate": False,
                                    "updated_at": message.date,
                                }
                            },
                        )

                    # Log filter matching details
                    if filter_result["matching_filters"]:
                        logger.info("Ad %s matches filters: %s", message.id, filter_result["matching_filters"])
                        for filter_id, details in filter_result["filter_details"].items():
                            logger.info("Filter %s (%s): matched", filter_id, details["name"])

                        # Update status to filtered
                        await db.incoming_messages.update_one(
                            {"id": message.id, "channel_id": message.chat_id},
                            {"$set": {"processing_status": "filtered", "updated_at": message.date}},
                        )
                    else:
                        logger.info("Ad %s does not match any filters", message.id)

                    # Forward if matches
                    for filter_id in filter_result["matching_filters"]:
                        await self._forward_post(message, real_estate_ad, filter_id)

            else:
                # Message has no text, skip processing
                logger.info("Message %s has no text, skipping LLM processing", message.id)
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {
                        "$set": {
                            "processing_status": "no_text",
                            "is_real_estate": False,
                            "processed_at": message.date,
                            "updated_at": message.date,
                        }
                    },
                )

            # Mark message as processed
            if real_estate_ad:
                # Already updated above
                pass
            else:
                # LLM determined this is not a real estate ad
                logger.info("Message %s not identified as real estate ad by LLM", message.id)
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {
                        "$set": {
                            "processing_status": "not_real_estate",
                            "is_real_estate": False,
                            "processed_at": message.date,
                            "updated_at": message.date,
                        }
                    },
                )

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error processing message: %s", e)
            # Update status to error
            try:
                db = mongodb.get_database()
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {
                        "$set": {
                            "processing_status": "error",
                            "parsing_errors": [str(e)],
                            "processed_at": message.date,
                            "updated_at": message.date,
                        }
                    },
                )
            except Exception as update_error:  # pylint: disable=broad-except
                logger.error("Error updating post status to error: %s", update_error)

    async def _forward_post(self, message: Optional[Message], real_estate_ad: Any, filter_id: str) -> None:
        """Forward post to user via bot"""
        try:
            # Get user ID from settings (your Telegram user ID)
            user_id = await user_service.get_primary_user_id()
            if not user_id:
                logger.warning("No authorized users found, skipping notification")
                return

            # Create formatted message with filter information
            formatted_message = await self._format_real_estate_message(real_estate_ad, message, filter_id)

            # Send to user via notification service
            # Create inline keyboard with settings button
            keyboard = [[InlineKeyboardButton("⚙️ Настроить фильтры", callback_data="open_settings")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if self.notification_service:
                await self.notification_service.send_message(
                    user_id=user_id, message=formatted_message, parse_mode="MarkdownV2", reply_markup=reply_markup
                )

            # Save forwarding record
            db = mongodb.get_database()
            
            # Get channel and topic information
            channel_info = await self._get_channel_info(real_estate_ad.original_channel_id)
            topic_title = None
            if real_estate_ad.original_topic_id:
                topic_title = await self._get_topic_title(real_estate_ad.original_channel_id, real_estate_ad.original_topic_id)
            
            forwarding_data = {
                "original_post_id": message.id,
                "original_channel_id": message.chat_id,
                "real_estate_ad_id": real_estate_ad.id,
                "filter_id": filter_id,
                "user_id": user_id,
                "processing_status": "forwarded",
                "message": formatted_message,
                "channel_id": real_estate_ad.original_channel_id,
                "channel_username": channel_info.get('username') if channel_info else None,
                "channel_title": channel_info.get('title') if channel_info else None,
                "topic_id": real_estate_ad.original_topic_id,
                "topic_title": topic_title,
            }
            await db.forwarded_posts.insert_one(forwarding_data)

            # Update post status to forwarded
            await db.incoming_messages.update_one(
                {"id": message.id, "channel_id": message.chat_id},
                {
                    "$set": {
                        "processing_status": "forwarded",
                        "forwarded": True,
                        "forwarded_at": message.date,
                        "forwarded_to": user_id,
                        "updated_at": message.date,
                    }
                },
            )

            logger.info("Forwarded post %s to user %s via filter %s", message.id, user_id, filter_id)

        except Exception as e:
            logger.error("Error forwarding post: %s", e)

    def _group_messages_by_grouped_id(self, messages: List[Any]) -> Dict[Any, List[Any]]:
        """Group messages by grouped_id to combine text + media messages"""
        groups: Dict[Any, List[Any]] = {}

        for message in messages:
            grouped_id = getattr(message, "grouped_id", None)
            if grouped_id:
                if grouped_id not in groups:
                    groups[grouped_id] = []
                groups[grouped_id].append(message)
            else:
                # Messages without grouped_id are treated as individual messages
                groups[f"single_{message.id}"] = [message]

        # Sort messages within each group by date
        for _, messages in groups.items():
            messages.sort(key=lambda x: x.date)

        return groups

    async def reprocess_recent_messages(self, num_messages: int, force: bool = False, user_id: Optional[int] = None, channel_id: Optional[int] = None) -> dict:
        """Reprocess N recent messages from monitored channels"""
        logger.info("Starting reprocess_recent_messages: num_messages=%s, force=%s, user_id=%s", num_messages, force, user_id)

        db = mongodb.get_database()
        stats = {
            "total_processed": 0,  # Number of advertisements processed
            "skipped": 0,  # Number of advertisements skipped
            "real_estate_ads": 0,  # Number of real estate advertisements found
            "spam_filtered": 0,  # Number of advertisements filtered as spam
            "not_real_estate": 0,  # Number of advertisements not about real estate
            "matched_filters": 0,  # Number of advertisements that matched user filters
            "forwarded": 0,  # Number of advertisements forwarded to user
            "errors": 0,  # Number of advertisements with processing errors
        }

        # Get monitored channels - use user subscriptions if available
        if channel_id:
            # Specific channel requested
            channels = [channel_id]
            logger.info("Using specific channel: %s", channel_id)
        elif user_id:
            user_channels = await self._get_user_monitored_channels()
            if user_channels:
                channels = list(user_channels.keys())
                logger.info("Using user monitored channels: %s", channels)
            else:
                logger.warning("No user subscriptions found, falling back to legacy channels")
                channels = self._get_monitored_channels()
        else:
            channels = self._get_monitored_channels()
            
        if not channels:
            logger.warning("No monitored channels found")
            return stats

        # Get recent messages from all channels and topics
        messages_to_fetch = num_messages * 10  # Increased multiplier to get more groups
        recent_messages = []

        for channel_id in channels:
            logger.info("Fetching messages from channel %s", channel_id)
            messages = []
            if not self.client:
                logger.error("Telegram client not initialized")
                continue
            
            # Get user subscriptions for this channel if user_id is provided
            channel_subscriptions = []
            if user_id and user_id in [sub.get("user_id") for sub in (await self._get_user_monitored_channels()).get(channel_id, [])]:
                channel_subscriptions = (await self._get_user_monitored_channels()).get(channel_id, [])
            
            async for message in self.client.iter_messages(int(channel_id), limit=messages_to_fetch):
                # Check if message matches user subscription criteria
                should_process = False
                
                if user_id and channel_subscriptions:
                    # Check against user subscription criteria
                    for subscription in channel_subscriptions:
                        sub_user_id = subscription["user_id"]
                        topic_id = subscription["topic_id"]
                        monitor_all_topics = subscription["monitor_all_topics"]
                        
                        if sub_user_id == user_id:
                            if monitor_all_topics:
                                should_process = True
                            elif topic_id:
                                should_process = await self._is_message_in_topic(message, channel_id, topic_id)
                            else:
                                should_process = True
                            break
                else:
                    # Legacy mode - process all messages
                    should_process = True
                
                if should_process:
                    messages.append(message)
                    logger.debug("Message %s: processing for user %s", message.id, user_id)
                else:
                    logger.debug("Message %s: skipping (doesn't match criteria)", message.id)

            recent_messages.extend(messages)
            logger.info("Fetched %s messages from channel %s", len(messages), channel_id)

        # Sort by date (newest first)
        recent_messages.sort(key=lambda x: x.date, reverse=True)

        # Group messages by grouped_id
        grouped_messages = self._group_messages_by_grouped_id(recent_messages)
        logger.info("Grouped %s messages into %s groups", len(recent_messages), len(grouped_messages))

        # Take only the requested number of groups (newest first)
        group_items = list(grouped_messages.items())
        group_items.sort(key=lambda x: x[1][0].date, reverse=True)
        logger.info("Available groups: %s", [f"{gid} ({len(msgs)} msgs)" for gid, msgs in group_items])

        group_items = group_items[:num_messages]
        grouped_messages = dict(group_items)

        logger.info("Processing %s advertisements (requested: %s)", len(grouped_messages), num_messages)

        # Process each group of messages (advertisements)
        for group_id, group_messages in grouped_messages.items():
            logger.info("Processing advertisement %s with %s messages", group_id, len(group_messages))

            # Combine text from all messages in the group
            combined_text = ""
            for message in group_messages:
                if message.text:
                    combined_text += message.text + "\n"

            # Use the first message as the main message for processing
            main_message = group_messages[0]
            main_message.text = combined_text.strip() if combined_text else ""

            # Debug: Print advertisement text
            if main_message.text:
                logger.info(
                    "Advertisement text: %s%s", main_message.text[:200], "..." if len(main_message.text) > 200 else ""
                )
            else:
                logger.info("Advertisement %s has no text content", group_id)

            # Check if main message already exists in database
            existing_post = await db.incoming_messages.find_one(
                {"id": main_message.id, "channel_id": main_message.chat_id}
            )

            if existing_post:
                current_status = existing_post.get("processing_status")

                if force:
                    # Force reprocessing - reset status
                    logger.info("Force reprocessing message %s (current status: %s)", main_message.id, current_status)
                    await db.incoming_messages.update_one(
                        {"id": main_message.id, "channel_id": main_message.chat_id},
                        {"$set": {"processing_status": "pending"}},
                    )
                else:
                    # Skip if already successfully processed (unless it's an error)
                    if current_status in [
                        "parsed",
                        "filtered",
                        "forwarded",
                        "spam_filtered",
                        "not_real_estate",
                        "media_only",
                    ]:
                        logger.debug(
                            "Message %s already processed with status %s, skipping", main_message.id, current_status
                        )
                        stats["skipped"] += 1
                        continue
                    elif current_status == "error":
                        logger.info("Message %s had error status, reprocessing", main_message.id)
                        await db.incoming_messages.update_one(
                            {"id": main_message.id, "channel_id": main_message.chat_id},
                            {"$set": {"processing_status": "pending"}},
                        )
                    else:
                        logger.info("Message %s has status %s, reprocessing", main_message.id, current_status)
                        await db.incoming_messages.update_one(
                            {"id": main_message.id, "channel_id": main_message.chat_id},
                            {"$set": {"processing_status": "pending"}},
                        )
            else:
                logger.info("Message %s not found in database, processing for first time", main_message.id)

            # Process the main message
            await self._process_message(main_message, force, user_id=user_id)

            # Only count messages with text (not media-only)
            if not self._is_media_only_message(main_message):
                stats["total_processed"] += 1

            # Update statistics based on final status
            post = await db.incoming_messages.find_one({"id": main_message.id, "channel_id": main_message.chat_id})

            if post:
                if post.get("processing_status") == "spam_filtered":
                    stats["spam_filtered"] += 1
                elif post.get("processing_status") == "media_only":
                    # Media-only messages are not counted in main stats
                    pass
                elif post.get("processing_status") == "not_real_estate":
                    stats["not_real_estate"] += 1
                elif post.get("processing_status") in ["parsed", "filtered", "forwarded"]:
                    stats["real_estate_ads"] += 1

                    # Check if it matched filters for this user
                    if user_id:
                        # Get real estate ad ID for this message
                        real_estate_ad = await db.real_estate_ads.find_one({
                            "original_post_id": main_message.id, 
                            "original_channel_id": main_message.chat_id
                        })
                        
                        if real_estate_ad:
                            # Check if there are any UserFilterMatch records for this user and ad
                            match_count = await db.user_filter_matches.count_documents({
                                "user_id": user_id,
                                "real_estate_ad_id": str(real_estate_ad["_id"])
                            })
                            if match_count > 0:
                                stats["matched_filters"] += 1
                            
                            # Check if it was forwarded to this user
                            forwarded_count = await db.outgoing_posts.count_documents({
                                "sent_to": str(user_id),
                                "real_estate_ad_id": str(real_estate_ad["_id"])
                            })
                            if forwarded_count > 0:
                                stats["forwarded"] += 1
                    else:
                        # Legacy mode - count all matches
                        if post.get("processing_status") == "forwarded":
                            stats["forwarded"] += 1
                elif post.get("processing_status") == "error":
                    stats["errors"] += 1

        logger.info("Reprocessing completed: %s", stats)
        return stats

    def _get_property_type_name(self, property_type: Any) -> str:
        """Convert property type enum to Russian name"""
        type_names = {
            "apartment": "Квартира",
            "house": "Дом",
            "room": "Комната",
            "hotel_room": "Гостиничный номер",
        }
        return str(type_names.get(property_type, property_type))

    async def _get_filter_name(self, filter_id: str) -> str:
        """Get filter name by MongoDB _id"""
        try:
            logger.info("Getting filter name for ID: %s", filter_id)
            object_id = ObjectId(filter_id)
            db = mongodb.get_database()

            # Try simple_filters collection first (where filters are actually stored)
            filter_doc = await db.simple_filters.find_one({"_id": object_id})
            logger.info("Filter document found in simple_filters: %s", filter_doc)

            if filter_doc:
                name = filter_doc["name"]
                logger.info("Filter name: %s", name)
                return str(name)

            # Fallback to filters collection
            filter_doc = await db.filters.find_one({"_id": object_id})
            logger.info("Filter document found in filters: %s", filter_doc)

            if filter_doc:
                name = filter_doc["name"]
                logger.info("Filter name: %s", name)
                return str(name)
            else:
                logger.warning("Filter not found for ID: %s", filter_id)
                return f"Фильтр {filter_id[:8]}..."

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error getting filter name: %s", e)
            return f"Фильтр {filter_id[:8]}..."

    def _get_message_link(self, channel_id: int, message_id: int, topic_id: Optional[int] = None) -> str:
        """Generate link to original message in channel"""
        # Convert to int if it's a Long object
        if hasattr(channel_id, "value") and channel_id.value is not None:
            channel_id = channel_id.value
        if hasattr(message_id, "value") and message_id.value is not None:
            message_id = message_id.value
        if topic_id is not None and hasattr(topic_id, "value") and topic_id.value is not None:
            topic_id = topic_id.value

        # For channels with topics, use @username/topic_id/message_id format
        if topic_id:
            # This is a topic-based channel, use the topic format
            # Get channel username from settings
            channel_username = settings.TELEGRAM_CHANNEL_USERNAME
            return f"https://t.me/{channel_username}/{topic_id}/{message_id}"

        # Regular channel, use c/channel_id/message_id format
        if channel_id < 0:
            channel_id = abs(channel_id) - 1000000000000
        return f"https://t.me/c/{channel_id}/{message_id}"

    def _escape_markdown(self, text: str) -> str:
        """Escape special characters for MarkdownV2"""
        if not text:
            return ""
        # Escape special characters for MarkdownV2
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def _get_yandex_maps_link(self, address: str, district: str = None, city: str = None) -> Optional[str]:
        """Generate Yandex Maps link for address"""
        if not address:
            return None
        
        try:
            # Clean and prepare address for URL encoding
            clean_address = address.strip()
            
            # Add district if provided and not already present
            if district and district not in clean_address:
                clean_address = f"{clean_address}, {district}"
            
            # Add city if provided and not already present
            if city and city not in clean_address:
                clean_address = f"{clean_address}, {city}"
            elif not city and "Ереван" not in clean_address and "Yerevan" not in clean_address:
                # Default to Yerevan if no city specified
                clean_address = f"{clean_address}, Ереван"
            
            # URL encode the address
            import urllib.parse
            encoded_address = urllib.parse.quote(clean_address)
            
            # Generate Yandex Maps link
            yandex_maps_url = f"https://yandex.ru/maps/?text={encoded_address}"
            
            return yandex_maps_url
            
        except Exception as e:
            logger.error("Error generating Yandex Maps link for address '%s': %s", address, e)
            return None

    async def _format_real_estate_message(
        self, real_estate_ad: Any, _original_message: Optional[Message], filter_id: Optional[str] = None
    ) -> str:
        """Format real estate ad for forwarding"""
        message = "🏠 *Найдено подходящее объявление\\!*\n\n"

        if real_estate_ad.property_type:
            property_name = self._get_property_type_name(real_estate_ad.property_type)
            message += f"*Тип:* {self._escape_markdown(property_name)}\n"
        if real_estate_ad.rooms_count:
            message += f"*Комнат:* {self._escape_markdown(str(real_estate_ad.rooms_count))}\n"
        if real_estate_ad.area_sqm:
            message += f"*Площадь:* {self._escape_markdown(str(real_estate_ad.area_sqm))} кв\\.м\n"
        if real_estate_ad.price:
            currency_symbol = "драм" if real_estate_ad.currency == "AMD" else real_estate_ad.currency
            message += f"*Цена:* {self._escape_markdown(f'{real_estate_ad.price:,} {currency_symbol}')}\n"
        if real_estate_ad.district:
            message += f"*Район:* {self._escape_markdown(real_estate_ad.district)}\n"
        if real_estate_ad.city:
            message += f"*Город:* {self._escape_markdown(real_estate_ad.city)}\n"
        if real_estate_ad.address:
            message += f"*Адрес:* {self._escape_markdown(real_estate_ad.address)}\n"
            # Add Yandex Maps link for address
            yandex_maps_link = self._get_yandex_maps_link(real_estate_ad.address, real_estate_ad.district, real_estate_ad.city)
            if yandex_maps_link:
                message += f"🗺️ [Посмотреть на карте]({yandex_maps_link})\n"
        if real_estate_ad.contacts:
            contacts_str = (
                ", ".join(real_estate_ad.contacts)
                if isinstance(real_estate_ad.contacts, list)
                else str(real_estate_ad.contacts)
            )
            message += f"*Контакты:* {self._escape_markdown(contacts_str)}\n"

        # Add channel and topic information
        channel_info = await self._get_channel_info(real_estate_ad.original_channel_id)
        if channel_info:
            channel_title = self._escape_markdown(channel_info.get('title', 'Неизвестный канал'))
            message += f"\n*📢 Канал:* {channel_title}"
            if channel_info.get('username'):
                username = channel_info['username'].lstrip('@')
                message += f" \\(@{username}\\)"
            
            # Add topic information if available
            if real_estate_ad.original_topic_id:
                topic_title = await self._get_topic_title(real_estate_ad.original_channel_id, real_estate_ad.original_topic_id)
                if topic_title:
                    message += f"\n*📌 Топик:* {self._escape_markdown(topic_title)}"
                else:
                    message += f"\n*📌 Топик:* #{real_estate_ad.original_topic_id}"

        # Add filter matching information
        # Note: Filter matching info is now handled via UserFilterMatch model
            if filter_id:
                filter_name = await self._get_filter_name(str(filter_id))
                message += f"*🎯 Активный фильтр:* {self._escape_markdown(filter_name)}\n"

        message += f"\n*Уверенность:* {self._escape_markdown(f'{real_estate_ad.parsing_confidence:.2f}')}\n"

        # Add original message link
        message_link = self._get_message_link(
            real_estate_ad.original_channel_id, real_estate_ad.original_post_id, real_estate_ad.original_topic_id
        )
        original_text = self._escape_markdown(real_estate_ad.original_message[:300])
        message += f"\n*Оригинальный текст:*\n{original_text}\\.\\.\\.\n\n"
        message += f"🔗 [Читать полностью]({message_link})"

        return message

    async def _get_channel_info(self, channel_id: int) -> Optional[Dict[str, str]]:
        """Get channel information by ID"""
        try:
            if not self.client:
                return None
            
            # Convert supergroup ID to regular ID for API call
            if channel_id < 0:
                regular_id = abs(channel_id) - 1000000000000
            else:
                regular_id = channel_id
            
            entity = await self.client.get_entity(regular_id)
            
            return {
                'id': channel_id,
                'title': getattr(entity, 'title', 'Неизвестный канал'),
                'username': getattr(entity, 'username', None)
            }
        except Exception as e:
            logger.error("Error getting channel info for %s: %s", channel_id, e)
            return None

    async def _get_topic_title(self, channel_id: int, topic_id: int) -> Optional[str]:
        """Get topic title by channel and topic ID"""
        try:
            if not self.client:
                return None
            
            from telethon import functions
            
            # Convert supergroup ID to regular ID for API call
            if channel_id < 0:
                regular_id = abs(channel_id) - 1000000000000
            else:
                regular_id = channel_id
            
            channel = await self.client.get_input_entity(regular_id)
            result = await self.client(functions.channels.GetForumTopicsByIDRequest(
                channel=channel,
                topics=[topic_id],
            ))
            
            if result.topics:
                return result.topics[0].title
            
            return None
        except Exception as e:
            logger.error("Error getting topic title for channel %s, topic %s: %s", channel_id, topic_id, e)
            return None

    async def _get_top_message_for_topic(self, channel_id: int, topic_id: int) -> Optional[int]:
        """Get the top_message id (thread root) for a given forum topic"""
        try:
            if not self.client:
                return None
            
            # Check cache first
            cache_key = (channel_id, topic_id)
            if cache_key in self.topic_cache:
                return self.topic_cache[cache_key]
            
            from telethon import functions, types
            
            # Convert supergroup ID to regular ID for API call
            if channel_id < 0:
                regular_id = abs(channel_id) - 1000000000000
            else:
                regular_id = channel_id
            
            channel = await self.client.get_input_entity(regular_id)
            result: types.messages.ForumTopics = await self.client(
                functions.channels.GetForumTopicsByIDRequest(
                    channel=channel,
                    topics=[topic_id],
                )
            )
            
            if not result.topics:
                logger.error("No such topic_id=%s in channel %s", topic_id, channel_id)
                return None
                
            top_message = result.topics[0].top_message
            
            # Cache the result
            self.topic_cache[cache_key] = top_message
            logger.debug("Cached top_message %s for channel %s, topic %s", top_message, channel_id, topic_id)
            
            return top_message
        except Exception as e:
            logger.error("Error getting top message for channel %s, topic %s: %s", channel_id, topic_id, e)
            return None

    async def _iter_topic_messages(self, channel_id: int, topic_id: int, limit: Optional[int] = None):
        """Iterate only messages that belong to the given forum topic"""
        try:
            if not self.client:
                return
            
            top_msg = await self._get_top_message_for_topic(channel_id, topic_id)
            if not top_msg:
                logger.error("Could not get top message for topic %s in channel %s", topic_id, channel_id)
                return
            
            # This yields *only* replies in that thread (the forum topic)
            async for msg in self.client.iter_messages(channel_id, reply_to=top_msg, limit=limit):
                yield msg
        except Exception as e:
            logger.error("Error iterating topic messages for channel %s, topic %s: %s", channel_id, topic_id, e)

    async def _is_message_in_topic(self, message, channel_id: int, topic_id: int) -> bool:
        """Check if a message belongs to a specific forum topic using top_message approach"""
        try:
            if not self.client:
                return False
            
            # Check cache first
            cache_key = (channel_id, topic_id)
            top_msg = self.topic_cache.get(cache_key)
            
            if top_msg is None:
                # Cache miss - get from API and cache it
                top_msg = await self._get_top_message_for_topic(channel_id, topic_id)
                if top_msg:
                    self.topic_cache[cache_key] = top_msg
                    logger.debug("Cached top_message %s for channel %s, topic %s", top_msg, channel_id, topic_id)
                else:
                    logger.warning("Could not get top message for topic %s in channel %s", topic_id, channel_id)
                    return False
            
            # Check if this message is a reply to the top message
            rt = getattr(message, "reply_to", None)
            reply_to_msg_id = getattr(rt, "reply_to_msg_id", None) if rt else None
            
            # Also check if this message IS the top message itself
            is_top_message = message.id == top_msg
            
            # Check if this message is a reply to the top message
            is_reply_to_top = reply_to_msg_id == top_msg
            
            result = is_top_message or is_reply_to_top
            
            logger.debug("Message %s in topic %s: is_top=%s, is_reply_to_top=%s, result=%s", 
                        message.id, topic_id, is_top_message, is_reply_to_top, result)
            
            return result
            
        except Exception as e:
            logger.error("Error checking if message %s is in topic %s: %s", message.id, topic_id, e)
            return False

    async def refilter_ads(self, count: int) -> dict:
        """Refilter existing ads without reprocessing using new UserFilterMatch architecture"""
        try:
            logger.info("Starting refilter for %s ads", count)

            # Get database connection
            db = mongodb.get_database()

            # Get recent real estate ads from database
            real_estate_ads_cursor = db.real_estate_ads.find().sort("_id", -1).limit(count)
            ads_list = []
            async for ad_doc in real_estate_ads_cursor:
                ads_list.append(ad_doc)

            logger.info("Found %s ads to refilter", len(ads_list))

            total_checked = 0
                # Note: matched_filters is now handled via UserFilterMatch model
            forwarded = 0
            errors = 0

            # Get all active filters grouped by user
            user_filters_cursor = db.simple_filters.find({"is_active": True})
            user_filters = {}
            async for filter_doc in user_filters_cursor:
                user_id = filter_doc.get("user_id")
                if user_id not in user_filters:
                    user_filters[user_id] = []
                user_filters[user_id].append(filter_doc)
            
            logger.info("Found filters for %s users", len(user_filters))

            if not user_filters:
                logger.warning("No active filters found")
                return {
                    "total_checked": len(ads_list),
                    "matched_filters": 0,
                    "forwarded": 0,
                    "errors": 0,
                    "message": "No active filters found",
                }

            from app.services.simple_filter_service import SimpleFilterService
            from app.services.user_filter_match_service import UserFilterMatchService
            
            filter_service = SimpleFilterService()
            match_service = UserFilterMatchService()

            # Process each ad
            for ad_doc in ads_list:
                try:
                    total_checked += 1

                    # Convert to RealEstateAd object
                    ad = RealEstateAd(**ad_doc)

                    # Check against all users' filters
                    for user_id, user_filter_docs in user_filters.items():
                        matching_filters = []
                        
                        for filter_doc in user_filter_docs:
                            filter_obj = SimpleFilter(**filter_doc)
                            
                            # Debug logging
                            logger.info("Checking ad %s (rooms=%s) against filter %s (min_rooms=%s, max_rooms=%s)", 
                                       ad.original_post_id, ad.rooms_count, filter_obj.name, 
                                       filter_obj.min_rooms, filter_obj.max_rooms)
                            
                            if filter_obj.matches(ad):
                                filter_id = str(filter_obj.id) if filter_obj.id else "unknown"
                                matching_filters.append(filter_id)
                                logger.info("Ad %s matched filter %s for user %s", 
                                           ad.original_post_id, filter_obj.name, user_id)
                            else:
                                logger.info("Ad %s did NOT match filter %s for user %s", 
                                           ad.original_post_id, filter_obj.name, user_id)
                        
                        # Create UserFilterMatch records for matching filters
                        if matching_filters:
                            # Note: matched_filters is now handled via UserFilterMatch model
                            
                            for filter_id in matching_filters:
                                # Create match record
                                match_id = await match_service.create_match(
                                    user_id=user_id,
                                    filter_id=filter_id,
                                    real_estate_ad_id=ad.id or str(ad_doc["_id"])
                                )
                                
                                if match_id:
                                    logger.info("Created UserFilterMatch: %s", match_id)
                                    
                                    # Forward the ad if not already forwarded for this user
                                    existing_forward = await db.outgoing_posts.find_one({
                                        "real_estate_ad_id": ad.id or str(ad_doc["_id"]),
                                        "sent_to": str(user_id)
                                    })
                                    
                                    if not existing_forward:
                                        try:
                                            # Forward post - _original_message is not used in _format_real_estate_message
                                            await self._forward_post(None, ad, filter_id)
                                            forwarded += 1
                                            logger.info("Ad %s forwarded to user %s", ad.original_post_id, user_id)
                                            
                                            # Mark match as forwarded
                                            await match_service.mark_as_forwarded(match_id)
                                            
                                        except Exception as e:  # pylint: disable=broad-except
                                            logger.error("Error forwarding ad %s to user %s: %s", 
                                                       ad.original_post_id, user_id, e)
                                            errors += 1

                except Exception as e:  # pylint: disable=broad-except
                    logger.error("Error processing ad %s: %s", ad_doc.get("_id"), e)
                    errors += 1

            result = {
                "total_checked": total_checked,
                # Note: matched_filters is now handled via UserFilterMatch model
                "forwarded": forwarded,
                "errors": errors,
            }

            logger.info("Refilter completed: %s", result)
            return result

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error in refilter_ads: %s", e)
            raise
