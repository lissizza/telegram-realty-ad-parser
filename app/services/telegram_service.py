import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

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

    def set_notification_service(self, bot: Any) -> None:
        """Set the notification service with bot instance"""
        self.notification_service = TelegramNotificationService(bot)

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
                        await self._process_message(event.message)
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
        """Handle new message from user subscribed channels"""
        try:
            message = event.message
            chat_id = event.chat_id
            
            logger.info("Processing message %s from channel %s", message.id, chat_id)
            
            # Get subscriptions for this channel
            channel_subscriptions = user_channels.get(chat_id, [])
            if not channel_subscriptions:
                logger.warning("No subscriptions found for channel %s", chat_id)
                return
            
            # Check if message matches any subscription criteria
            rt = getattr(message, "reply_to", None)
            reply_to_msg_id = getattr(rt, "reply_to_msg_id", None) if rt else None
            
            logger.info("Message %s: reply_to=%s, reply_to_msg_id=%s", message.id, rt, reply_to_msg_id)
            
            # Process message for each matching subscription
            for subscription in channel_subscriptions:
                user_id = subscription["user_id"]
                topic_id = subscription["topic_id"]
                monitor_all_topics = subscription["monitor_all_topics"]
                monitored_topics = subscription["monitored_topics"]
                
                # Check if message matches subscription criteria
                should_process = False
                
                if monitor_all_topics:
                    # Monitor all topics in this channel
                    should_process = True
                    logger.info("Processing message for user %s (monitor_all_topics=True)", user_id)
                elif topic_id and reply_to_msg_id == topic_id:
                    # Monitor specific topic
                    should_process = True
                    logger.info("Processing message for user %s (topic_id=%s)", user_id, topic_id)
                elif monitored_topics and reply_to_msg_id in monitored_topics:
                    # Monitor specific topics from list
                    should_process = True
                    logger.info("Processing message for user %s (monitored_topics=%s)", user_id, monitored_topics)
                elif not topic_id and not monitored_topics and not monitor_all_topics:
                    # Monitor main channel (no topic filtering)
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
            await self._process_message(message, force=False)
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
                            # Try to parse as integer
                            channel_id_int = int(channel_id)
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

    def _is_message_in_topic(self, message: Message, topic_id: int) -> bool:
        """Check if message is in the specified topic (old method - kept for compatibility)"""
        try:
            # Check if message is in the specific topic
            if message.reply_to and hasattr(message.reply_to, "reply_to_top_id"):
                if message.reply_to.reply_to_top_id == topic_id:
                    logger.debug("Message %s is in topic %s (via reply_to)", message.id, topic_id)
                    return True

            # For messages without reply_to, we cannot determine the topic
            # This is a limitation of Telegram API - we need reply_to to identify topics
            # We'll be strict and only process messages with reply_to
            logger.debug("Message %s has no reply_to, cannot determine topic, skipping", message.id)
            return False

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error checking topic: %s", e)
            return False

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
            monitored_subchannels = self._get_monitored_subchannels()

            if not monitored_subchannels:
                # If no subchannels configured, process all messages
                return True

            # Since we already filtered messages by topic in reprocess_recent_messages,
            # we can assume all messages are from the correct topic
            for channel_id, _ in monitored_subchannels:
                if message.chat_id == channel_id:
                    logger.debug(
                        "Message %s from channel %s, processing (already filtered by topic)", message.id, channel_id
                    )
                    return True

            return False
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

    async def _process_message(self, message: Message, force: bool = False) -> None:
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
                        filter_result = await self.simple_filter_service.check_filters(real_estate_ad)

                        # Update ad with filter matching information
                        real_estate_ad.matched_filters = filter_result["matching_filters"]
                        real_estate_ad.should_forward = filter_result["should_forward"]

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

    async def _forward_post(self, message: Message, real_estate_ad: Any, filter_id: str) -> None:
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
                    user_id=user_id, message=formatted_message, parse_mode="Markdown", reply_markup=reply_markup
                )

            # Save forwarding record
            db = mongodb.get_database()
            forwarding_data = {
                "original_post_id": message.id,
                "original_channel_id": message.chat_id,
                "real_estate_ad_id": real_estate_ad.id,
                "filter_id": filter_id,
                "user_id": user_id,
                "processing_status": "forwarded",
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

    async def reprocess_recent_messages(self, num_messages: int, force: bool = False) -> dict:
        """Reprocess N recent messages from monitored channels"""
        logger.info("Starting reprocess_recent_messages: num_messages=%s, force=%s", num_messages, force)

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

        # Get monitored channels
        channels = self._get_monitored_channels()
        if not channels:
            logger.warning("No monitored channels found")
            return stats

        # Get recent messages from all channels and topics
        messages_to_fetch = num_messages * 10  # Increased multiplier to get more groups
        recent_messages = []

        for channel_id in channels:
            # Process only messages from main topic (reply_to_msg_id=2629)
            # Skip all other subchannels
            logger.info("Fetching messages from channel %s (main topic only - reply_to_msg_id=2629)", channel_id)
            messages = []
            if not self.client:
                logger.error("Telegram client not initialized")
                continue
            async for message in self.client.iter_messages(int(channel_id), limit=messages_to_fetch):
                # Process only messages from main topic
                rt = getattr(message, "reply_to", None)
                reply_to_msg_id = getattr(rt, "reply_to_msg_id", None) if rt else None

                if rt and reply_to_msg_id == 2629:
                    # Message from main topic with real estate ads, process it
                    messages.append(message)
                    logger.debug("Message %s: reply_to_msg_id=%s (main topic, processing)", message.id, reply_to_msg_id)
                else:
                    # Message from other subchannels or no reply_to, skip it
                    logger.debug(
                        "Message %s: reply_to_msg_id=%s (subchannel or no reply_to, skipping)",
                        message.id,
                        reply_to_msg_id,
                    )

            recent_messages.extend(messages)
            logger.info("Fetched %s messages from channel %s (main topic only)", len(messages), channel_id)

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
            await self._process_message(main_message, force)

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

                    # Check if it matched filters
                    real_estate_ad = await db.real_estate_ads.find_one(
                        {"original_post_id": main_message.id, "original_channel_id": main_message.chat_id}
                    )

                    if real_estate_ad and real_estate_ad.get("matched_filters"):
                        stats["matched_filters"] += 1

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

    async def _format_real_estate_message(
        self, real_estate_ad: Any, _original_message: Message, filter_id: Optional[str] = None
    ) -> str:
        """Format real estate ad for forwarding"""
        message = "🏠 **Найдено подходящее объявление!**\n\n"

        if real_estate_ad.property_type:
            property_name = self._get_property_type_name(real_estate_ad.property_type)
            message += f"**Тип:** {property_name}\n"
        if real_estate_ad.rooms_count:
            message += f"**Комнат:** {real_estate_ad.rooms_count}\n"
        if real_estate_ad.area_sqm:
            message += f"**Площадь:** {real_estate_ad.area_sqm} кв.м\n"
        if real_estate_ad.price:
            currency_symbol = "драм" if real_estate_ad.currency == "AMD" else real_estate_ad.currency
            message += f"**Цена:** {real_estate_ad.price:,} {currency_symbol}\n"
        if real_estate_ad.district:
            message += f"**Район:** {real_estate_ad.district}\n"
        if real_estate_ad.address:
            message += f"**Адрес:** {real_estate_ad.address}\n"
        if real_estate_ad.contacts:
            contacts_str = (
                ", ".join(real_estate_ad.contacts)
                if isinstance(real_estate_ad.contacts, list)
                else str(real_estate_ad.contacts)
            )
            message += f"**Контакты:** {contacts_str}\n"

        # Add filter matching information
        if real_estate_ad.matched_filters:
            message += f"\n**✅ Соответствует фильтрам:** {len(real_estate_ad.matched_filters)}\n"
            if filter_id:
                filter_name = await self._get_filter_name(str(filter_id))
                message += f"**🎯 Активный фильтр:** {filter_name}\n"

        message += f"\n**Уверенность:** {real_estate_ad.parsing_confidence:.2f}\n"

        # Add original message link
        message_link = self._get_message_link(
            real_estate_ad.original_channel_id, real_estate_ad.original_post_id, real_estate_ad.original_topic_id
        )
        message += f"\n**Оригинальный текст:**\n{real_estate_ad.original_message[:300]}...\n\n"
        message += f"🔗 [Читать полностью]({message_link})"

        return message

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
            matched_filters = 0
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
                            
                            if filter_obj.matches(ad):
                                filter_id = str(filter_obj.id) if filter_obj.id else "unknown"
                                matching_filters.append(filter_id)
                                logger.info("Ad %s matched filter %s for user %s", 
                                           ad.original_post_id, filter_obj.name, user_id)
                        
                        # Create UserFilterMatch records for matching filters
                        if matching_filters:
                            matched_filters += len(matching_filters)
                            
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
                                            # Create a mock message object for forwarding
                                            mock_message = MagicMock()
                                            mock_message.chat_id = ad.original_channel_id
                                            mock_message.id = ad.original_post_id

                                            await self._forward_post(mock_message, ad, filter_id)
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
                "matched_filters": matched_filters,
                "forwarded": forwarded,
                "errors": errors,
            }

            logger.info("Refilter completed: %s", result)
            return result

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error in refilter_ads: %s", e)
            raise
