import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telethon import TelegramClient, events
from telethon.tl.types import Message

from app.core.config import settings
from app.db.mongodb import mongodb
from app.exceptions import LLMQuotaExceededError
from app.models.incoming_message import IncomingMessage
from app.models.status_enums import IncomingMessageStatus, RealEstateAdStatus, OutgoingPostStatus
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
        self._initialized = False
        # Store active handlers for cleanup
        self._active_handlers: List[Any] = []
        # Store current user channels for handlers
        self._current_user_channels: Dict[int, List[Dict]] = {}

    def set_notification_service(self, bot: Any) -> None:
        """Set the notification service with bot instance"""
        logger.info("Setting notification service with bot instance")
        self.notification_service = TelegramNotificationService(bot)
        logger.info("Notification service set successfully")

    def _generate_message_hash(self, message_text: str) -> str:
        """Generate hash for message content to detect duplicates"""
        # Normalize text: remove extra whitespace, convert to lowercase
        normalized_text = ' '.join(message_text.strip().split()).lower()
        # Generate SHA-256 hash
        return hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()

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
        """Start monitoring Telegram channels - NEW VERSION: monitors all channels, checks all filters"""
        if self.is_monitoring:
            logger.warning("Monitoring is already active")
            return

        try:
            # Initialize Telegram client only if not already exists and not initialized
            if not self.client or not self._initialized:
                if self.client:
                    # Clean up existing client if it exists but not properly initialized
                    try:
                        await self.client.disconnect()
                    except Exception:
                        pass  # Ignore errors during cleanup
                
                self.client = TelegramClient(
                    settings.TELEGRAM_SESSION_NAME, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH
                )
                await self.client.start(phone=settings.TELEGRAM_PHONE)
                self._initialized = True
                logger.info("Telegram client initialized successfully")
            elif not self.client.is_connected():
                await self.client.start(phone=settings.TELEGRAM_PHONE)
                logger.info("Telegram client reconnected")

            # Get monitored channels from new system
            monitored_channels = await self._get_monitored_channels_new()
            
            if not monitored_channels:
                logger.warning("No monitored channels found")
                return

            logger.info("Monitoring %d channels: %s", len(monitored_channels), [c["channel_id"] for c in monitored_channels])
            
            # Register handlers for all monitored channels
            await self._register_monitored_channel_handlers(monitored_channels)

            self.is_monitoring = True
            logger.info("Started monitoring Telegram channels")

            # Start the client in background without blocking
            logger.info("Starting Telegram client in background...")
            
            # Check if client is connected
            if self.client.is_connected():
                logger.info("Telegram client is already connected")
            else:
                logger.warning("Telegram client is not connected, attempting to start...")
                try:
                    await self.client.start(phone=settings.TELEGRAM_PHONE)
                    logger.info("Telegram client started successfully")
                except Exception as e:
                    logger.error("Failed to start Telegram client: %s", e)
                    raise
            
            # Create background task with error handling
            async def run_client():
                try:
                    logger.info("Telegram client background task started")
                    await self.client.run_until_disconnected()
                    logger.info("Telegram client disconnected")
                except Exception as e:
                    logger.error("Error in Telegram client background task: %s", e)
            
            asyncio.create_task(run_client())
            logger.info("Telegram client background task created")
            
            # Load recent messages from monitored channels
            await self._load_recent_messages_from_monitored_channels(monitored_channels, settings.STARTUP_MESSAGE_LIMIT)

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error starting monitoring: %s", e)
            raise

    async def _get_monitored_channels_new(self) -> List[Dict]:
        """Get monitored channels from new system (not tied to users)"""
        try:
            db = mongodb.get_database()
            channels = []
            async for doc in db.monitored_channels.find({"is_active": True}):
                channels.append({
                    "channel_id": int(doc["channel_id"]),
                    "channel_username": doc.get("channel_username"),
                    "channel_title": doc.get("channel_title"),
                    "topic_id": doc.get("topic_id"),
                    "monitor_all_topics": doc.get("monitor_all_topics", False),
                    "monitored_topics": doc.get("monitored_topics", [])
                })
            
            logger.info("Found %d active monitored channels", len(channels))
            return channels
            
        except Exception as e:
            logger.error("Error getting monitored channels: %s", e)
            return []

    async def _register_monitored_channel_handlers(self, monitored_channels: List[Dict]) -> None:
        """Register event handlers for monitored channels"""
        try:
            # Group channels by ID for handlers
            channel_ids = [c["channel_id"] for c in monitored_channels]
            
            if not channel_ids:
                logger.warning("No channel IDs to register handlers for")
                return
            
            logger.info("Registering handlers for %d channels: %s", len(channel_ids), channel_ids)
            
            # Create a single handler for all channels
            @self.client.on(events.NewMessage(chats=channel_ids))
            async def handle_new_message(event: events.NewMessage.Event) -> None:
                """Handle new message from any monitored channel"""
                try:
                    message = event.message
                    chat_id = event.chat_id
                    
                    # Process message for all users with active filters (new architecture)
                    await self._process_message(message)
                    
                except Exception as e:
                    logger.error("Error handling new message: %s", e)
            
            logger.info("Registered handlers for monitored channels")
            
        except Exception as e:
            logger.error("Error registering monitored channel handlers: %s", e)

    async def _load_recent_messages_from_monitored_channels(self, monitored_channels: List[Dict], limit: int = 100) -> None:
        """Load recent messages from monitored channels on startup - only process messages we missed during downtime"""
        try:
            logger.info("Loading recent messages from %d monitored channels (limit: %d per channel)", len(monitored_channels), limit)

            total_messages = 0
            processed_messages = 0
            skipped_messages = 0
            error_messages = 0

            for channel in monitored_channels:
                channel_id = channel["channel_id"]
                try:
                    logger.info("Checking for missed messages in channel %s", channel_id)

                    channel_processed = 0
                    channel_skipped = 0
                    channel_errors = 0

                    # Load messages one by one and stop when we find already processed messages
                    async for message in self.client.iter_messages(channel_id, limit=limit):
                        total_messages += 1

                        try:
                            # Check if message was already successfully processed
                            db = mongodb.get_database()
                            existing_post = await db.incoming_messages.find_one({
                                "id": message.id,
                                "channel_id": message.chat_id
                            })

                            if existing_post:
                                current_status = existing_post.get("processing_status")
                                # If already successfully processed, stop processing this channel
                                # (we've caught up with previously processed messages)
                                if current_status in [IncomingMessageStatus.PARSED, IncomingMessageStatus.NOT_REAL_ESTATE, IncomingMessageStatus.SPAM_FILTERED, IncomingMessageStatus.MEDIA_ONLY]:
                                    logger.info("Found already processed message %s in channel %s, stopping catch-up for this channel", message.id, channel_id)
                                    skipped_messages += 1
                                    channel_skipped += 1
                                    break  # Stop processing this channel, we've caught up
                                elif current_status == IncomingMessageStatus.ERROR:
                                    logger.info("Message %s had error status, reprocessing", message.id)
                                    await self._process_message(message)
                                    processed_messages += 1
                                    channel_processed += 1
                                else:
                                    logger.info("Message %s has status %s, processing", message.id, current_status)
                                    await self._process_message(message)
                                    processed_messages += 1
                                    channel_processed += 1
                            else:
                                # New message, process it
                                await self._process_message(message)
                                processed_messages += 1
                                channel_processed += 1

                        except Exception as e:
                            logger.error("Error processing message %s from channel %s: %s", message.id, channel_id, e)
                            error_messages += 1
                            channel_errors += 1

                    logger.info("Channel %s: processed %d, skipped %d, errors %d",
                               channel_id, channel_processed, channel_skipped, channel_errors)

                except Exception as e:
                    logger.error("Error loading messages from channel %s: %s", channel_id, e)
                    continue

            logger.info("Catch-up completed: checked %d total messages, processed %d new/missed, skipped %d already-processed, errors %d",
                       total_messages, processed_messages, skipped_messages, error_messages)

        except Exception as e:
            logger.error("Error in catch-up loading from monitored channels: %s", e)

    async def _load_recent_messages_from_channels(self, user_channels: Dict[int, List[Dict]], limit: int = 100) -> None:
        """Load recent messages from subscribed channels on startup with proper topic filtering"""
        try:
            logger.info("Loading recent messages from %d channels (limit: %d)", len(user_channels), limit)
            
            total_loaded = 0
            total_processed = 0
            total_messages_found = 0
            
            for channel_id, subscriptions in user_channels.items():
                try:
                    logger.info("Loading messages from channel %s", channel_id)
                    
                    # Get the channel entity
                    channel_entity = await self.client.get_entity(channel_id)
                    
                    # Load recent messages
                    messages = await self.client.get_messages(channel_entity, limit=limit)
                    
                    logger.info("Found %d messages in channel %s", len(messages), channel_id)
                    total_messages_found += len(messages)
                    
                    # Process each message
                    for message in messages:
                        # Check if message already exists in database
                        db = mongodb.get_database()
                        existing_message = await db.incoming_messages.find_one({
                            "id": message.id,
                            "channel_id": message.chat_id
                        })
                        
                        if existing_message:
                            logger.info("Message %s already exists in database, stopping processing (stop_on_existing=True)", message.id)
                            break  # Stop processing on first existing message
                        
                        # Process message for each matching subscription
                        for subscription in subscriptions:
                            user_id = subscription["user_id"]
                            topic_id = subscription["topic_id"]
                            monitor_all_topics = subscription["monitor_all_topics"]
                            monitored_topics = subscription["monitored_topics"]
                            
                            # Check if message matches subscription criteria
                            should_process = False
                            
                            if monitor_all_topics:
                                should_process = True
                                logger.info("Processing message %s for user %s (monitor all topics)", message.id, user_id)
                            elif topic_id and monitored_topics:
                                # Check if message is in monitored topics
                                if topic_id in monitored_topics:
                                    should_process = True
                                    logger.info("Processing message %s for user %s (monitored topic %s)", message.id, user_id, topic_id)
                            elif topic_id:
                                # Use top_message approach for single topic
                                if await self._is_message_in_topic(message, channel_id, topic_id):
                                    should_process = True
                                    logger.info("Processing message %s for user %s (topic %s)", message.id, user_id, topic_id)
                            else:
                                # Monitor main channel (no topic filtering) - process all messages
                                should_process = True
                                logger.info("Processing message %s for user %s (main channel)", message.id, user_id)
                            
                            if should_process:
                                # Process message through full pipeline (LLM + filters)
                                await self._process_message_for_user(message, user_id, subscription)
                                total_processed += 1
                        
                        total_loaded += 1
                        
                except Exception as e:
                    logger.error("Error loading messages from channel %s: %s", channel_id, e)
                    continue
            
            logger.info("Found %d total messages, loaded %d text messages, processed %d", total_messages_found, total_loaded, total_processed)
            
        except Exception as e:
            logger.error("Error loading recent messages: %s", e)



    async def _register_channel_handlers(self, user_channels: Dict[int, List[Dict]]) -> None:
        """Register event handlers for each monitored channel"""
        try:
            # Clear existing handlers
            await self._clear_handlers()
            
            channel_ids = list(user_channels.keys())
            logger.info("Registering handlers for channels: %s", channel_ids)
            
            # Store user_channels for use in handler
            self._current_user_channels = user_channels
            
            # Register separate handler for each channel
            for channel_id in channel_ids:
                @self.client.on(events.NewMessage(chats=[channel_id]))
                async def handle_new_message_user(event: events.NewMessage.Event) -> None:
                    await self._handle_user_subscription_message(event, self._current_user_channels)
                
                # Store handler reference for cleanup
                self._active_handlers.append(handle_new_message_user)
            
            logger.info("Registered separate handlers for %d channels", len(channel_ids))
            
        except Exception as e:
            logger.error("Error registering channel handlers: %s", e)
            raise

    async def _clear_handlers(self) -> None:
        """Clear all active event handlers"""
        try:
            # Note: Telethon doesn't provide easy way to remove specific handlers
            # We'll rely on re-registering handlers with updated channels
            self._active_handlers.clear()
            logger.info("Cleared all event handlers")
        except Exception as e:
            logger.error("Error clearing handlers: %s", e)

    async def update_channel_monitoring(self) -> None:
        """Update channel monitoring when subscriptions change"""
        try:
            if not self.is_monitoring:
                logger.warning("Monitoring not active, cannot update channels")
                return
                
            # Get monitored channels from new system
            monitored_channels = await self._get_monitored_channels_new()
            
            if not monitored_channels:
                logger.warning("No monitored channels found for monitoring update")
                return
                
            # Re-register handlers with updated channels
            await self._register_monitored_channel_handlers(monitored_channels)
            
            logger.info("Updated channel monitoring with %d channels", len(monitored_channels))
            
        except Exception as e:
            logger.error("Error updating channel monitoring: %s", e)

    # Removed: _handle_user_subscription_message - replaced by new system

    # Removed: _process_message_for_user - replaced by new system


    async def _get_monitored_channel_id_by_telegram_id(self, telegram_channel_id: int) -> Optional[str]:
        """Get monitored channel ID by Telegram channel ID"""
        try:
            db = mongodb.get_database()
            if db is None:
                return None
                
            # Convert Telegram channel ID to string format, removing -100 prefix
            channel_id_str = str(telegram_channel_id)
            if channel_id_str.startswith('-100'):
                channel_id_str = channel_id_str[4:]  # Remove -100 prefix
            
            # Find monitored channel by channel_id
            channel_doc = await db.monitored_channels.find_one({
                "channel_id": channel_id_str,
                "is_active": True
            })
            
            if channel_doc:
                return str(channel_doc["_id"])
            
            return None
            
        except Exception as e:
            logger.error("Error getting monitored channel ID: %s", e)
            return None

    async def stop_monitoring(self) -> None:
        """Stop monitoring Telegram channels"""
        if not self.is_monitoring:
            logger.warning("Monitoring is not active")
            return

        try:
            if self.client:
                await self.client.disconnect()
                self.client = None
            self.is_monitoring = False
            self._initialized = False
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

    def _get_monitored_channels_legacy(self) -> List[int]:
        """Get list of monitored channel IDs from settings (legacy fallback)"""
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

    # Removed: _get_user_monitored_channels - replaced by new system

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
                return False
            else:
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
            # Spam and moderation messages
            "заблокировали",
            "lolsbot",
            "antispam",
            "антиспам",
            "спам",
            "botcatcher",
            "бесплатный антиспам",
            "usdt за наличные",
            "курс честный",
            "безопасная встреча",
            "билеты",
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
        """Process incoming message - NEW VERSION: processes all messages and checks against all filters"""
        real_estate_ad = None  # Initialize variable
        try:
            # Log message details for debugging
            # Check if message is from monitored subchannel (topic)
            if not self._is_from_monitored_subchannel(message):
                return

            # Check if message is media-only (skip processing completely)
            if self._is_media_only_message(message):
                return
            
            # Log only messages that will be processed
            logger.info("Processing message %s from channel %s", message.id, message.chat_id)
            if message.text:
                logger.info("Message text: %s", message.text[:200] + "..." if len(message.text) > 200 else message.text)

            # Generate message hash for duplicate detection
            message_text = message.text or ""
            message_hash = self._generate_message_hash(message_text)
            
            # Check if message already processed by ID
            db = mongodb.get_database()
            existing_post = await db.incoming_messages.find_one({"id": message.id, "channel_id": message.chat_id})

            if existing_post:
                # Check if we need to reprocess (e.g., if status is ERROR or force=True)
                if not force and existing_post.get("processing_status") not in [IncomingMessageStatus.ERROR]:
                    return

                logger.info(
                    "Reprocessing message %s (previous status: %s)",
                    message.id,
                    existing_post.get("processing_status"),
                )
            
            # Check if we have a duplicate by hash (different message ID but same content)
            # Exclude current message from search
            duplicate_by_hash = await db.incoming_messages.find_one({
                "message_hash": message_hash,
                "id": {"$ne": message.id}  # Exclude current message
            })
            
            if duplicate_by_hash and not force:
                logger.info("Found duplicate message by hash: %s (original: %s)", message.id, duplicate_by_hash["id"])
                
                # Save the duplicate message with DUPLICATE status
                channel_title = "Unknown"
                try:
                    if message.chat and hasattr(message.chat, "title"):
                        channel_title = message.chat.title
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning("Could not get channel title for message %s: %s", message.id, e)
                
                duplicate_data = {
                    "id": message.id,
                    "channel_id": message.chat_id,
                    "channel_title": channel_title,
                    "message": message_text,
                    "message_hash": message_hash,
                    "date": message.date,
                    "views": getattr(message, "views", None),
                    "forwards": getattr(message, "forwards", None),
                    "processing_status": IncomingMessageStatus.DUPLICATE,
                    "is_real_estate": duplicate_by_hash.get("is_real_estate"),
                    "real_estate_ad_id": duplicate_by_hash.get("real_estate_ad_id"),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
                
                await db.incoming_messages.insert_one(duplicate_data)
                logger.info("Saved duplicate message %s with DUPLICATE status", message.id)
                
                # Check if the original message was parsed successfully
                if duplicate_by_hash.get("real_estate_ad_id"):
                    # Get the parsed real estate ad
                    real_estate_ad_doc = await db.real_estate_ads.find_one({"_id": ObjectId(duplicate_by_hash["real_estate_ad_id"])})
                    
                    if real_estate_ad_doc:
                        # Create RealEstateAd object from the duplicate
                        real_estate_ad = RealEstateAd(**real_estate_ad_doc)
                        
                        # Forward the duplicate using the existing parsed data (without re-parsing with LLM)
                        await self._check_filters_for_all_users(real_estate_ad, message)
                        
                logger.info("Duplicate message %s processed without LLM parsing", message.id)
                return

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
                "message_hash": message_hash,
                "date": message.date,
                "views": getattr(message, "views", None),
                "forwards": getattr(message, "forwards", None),
                "replies": None,  # Skip replies object as it's not serializable
                "media_type": None,
                "media_url": None,
                "processing_status": IncomingMessageStatus.PENDING,
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

            # Save or update IncomingMessage first
            if existing_post:
                # Update existing post
                result = await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id}, {"$set": post_data}
                )
                incoming_message_id = str(existing_post["_id"])
            else:
                # Insert new post
                result = await db.incoming_messages.insert_one(post_data)
                incoming_message_id = str(result.inserted_id)

            # Try to parse as real estate ad using LLM
            message_text = message.text or ""
            logger.info("Message %s: text='%s', has_text=%s", message.id, message_text, bool(message.text))

            # Skip technical bot messages
            if self._is_technical_bot_message(message_text):
                logger.info("Message %s is a technical bot message, skipping", message.id)
                return

            if message_text:
                # Let LLM determine if it's a real estate ad
                logger.info("Processing message %s with LLM", message.id)

                # Update status to parsing
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {"$set": {"processing_status": IncomingMessageStatus.PROCESSING, "updated_at": message.date}},
                )

                # Create IncomingMessage object for parsing
                topic_id = settings.get_topic_id_for_channel(message.chat_id)

                incoming_message_obj = IncomingMessage(
                    id=message.id,
                    channel_id=message.chat_id,
                    topic_id=topic_id,
                    channel_title=channel_title,
                    message=message_text,
                    date=message.date,
                    processing_status=IncomingMessageStatus.PROCESSING,
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
                        # Save parsed ad first
                        ad_data = real_estate_ad.model_dump(exclude={"id"}, by_alias=False)
                        result = await db.real_estate_ads.replace_one(
                            {"original_post_id": message.id}, ad_data, upsert=True
                        )
                        if result.upserted_id:
                            real_estate_ad.id = str(result.upserted_id)
                            logger.info("Created new RealEstateAd with id: %s", real_estate_ad.id)
                        else:
                            # Find existing record to get its ID
                            existing = await db.real_estate_ads.find_one({"original_post_id": message.id})
                            if existing:
                                real_estate_ad.id = str(existing["_id"])
                                logger.info("Updated existing RealEstateAd with id: %s", real_estate_ad.id)

                        # Update post status to parsed
                        await db.incoming_messages.update_one(
                            {"id": message.id, "channel_id": message.chat_id},
                            {
                                "$set": {
                                    "processing_status": IncomingMessageStatus.PARSED,
                                    "is_real_estate": True,
                                    "real_estate_confidence": real_estate_ad.parsing_confidence,
                                    "real_estate_ad_id": real_estate_ad.id,
                                    "updated_at": message.date,
                                }
                            },
                        )

                        # NEW: Check filters for ALL users (not just one specific user)
                        await self._check_filters_for_all_users(real_estate_ad, message)

                    else:
                        # LLM determined this is not real estate
                        await db.incoming_messages.update_one(
                            {"id": message.id, "channel_id": message.chat_id},
                            {
                                "$set": {
                                    "processing_status": IncomingMessageStatus.NOT_REAL_ESTATE,
                                    "is_real_estate": False,
                                    "updated_at": message.date,
                                }
                            },
                        )

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
                            "processing_status": IncomingMessageStatus.NOT_REAL_ESTATE,
                            "is_real_estate": False,
                            "processed_at": message.date,
                            "updated_at": message.date,
                        }
                    },
                )

        except LLMQuotaExceededError as e:
            logger.error("LLM quota exceeded while processing message %s: %s", message.id, e)
            # Update status to error with quota info
            try:
                db = mongodb.get_database()
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {
                        "$set": {
                            "processing_status": IncomingMessageStatus.ERROR,
                            "parsing_errors": [f"LLM quota exceeded ({e.provider}): {e.message}"],
                            "processed_at": message.date,
                            "updated_at": message.date,
                        }
                    },
                )
            except Exception as update_error:  # pylint: disable=broad-except
                logger.error("Error updating message status to error: %s", update_error)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error processing message: %s", e)
            # Update status to error
            try:
                db = mongodb.get_database()
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {
                        "$set": {
                            "processing_status": IncomingMessageStatus.ERROR,
                            "parsing_errors": [str(e)],
                            "processed_at": message.date,
                            "updated_at": message.date,
                        }
                    },
                )
            except Exception as update_error:  # pylint: disable=broad-except
                logger.error("Error updating post status to error: %s", update_error)

    async def _check_filters_for_all_users(self, real_estate_ad: RealEstateAd, message: Message) -> None:
        """Check filters for ALL users and forward to matching users"""
        try:
            # Check if ad has already been forwarded (prevent duplicates)
            if real_estate_ad.processing_status == RealEstateAdStatus.FORWARDED:
                logger.info("Ad %s already forwarded, skipping filter check", message.id)
                return
            
            db = mongodb.get_database()
            
            # Get all active filters from all users
            all_filters = await db.simple_filters.find({"is_active": True}).to_list(length=None)
            
            if not all_filters:
                logger.info("No active filters found for ad %s", message.id)
                return
            
            logger.info("Checking %d filters for ad %s", len(all_filters), message.id)
            
            # Get channel selection service
            from app.services.user_channel_selection_service import UserChannelSelectionService
            selection_service = UserChannelSelectionService()
            
            # Check each filter
            for filter_doc in all_filters:
                try:
                    # Create SimpleFilter object
                    filter_obj = SimpleFilter(**filter_doc)
                    user_id = filter_obj.user_id
                    
                    # Check if user has selected this channel
                    # Use normalized channel ID format
                    is_channel_selected = await selection_service.is_channel_selected_by_user(user_id, message.chat_id)
                    
                    if not is_channel_selected:
                        logger.info("User %s has not selected channel %s, skipping filter '%s'", user_id, message.chat_id, filter_obj.name)
                        continue
                    
                    logger.info("Checking filter '%s' (user %s) for ad %s", filter_obj.name, user_id, message.id)
                    
                    # Get price filters for this filter
                    from app.services.price_filter_service import PriceFilterService
                    price_filter_service = PriceFilterService()
                    filter_id = str(filter_doc["_id"])  # Use the _id from the database document
                    price_filters = await price_filter_service.get_price_filters_by_filter_id(filter_id)
                    
                    # Check if this specific filter matches the ad
                    if filter_obj.matches_with_price_filters(real_estate_ad, price_filters):
                        logger.info("Ad %s matches filter '%s' for user %s", message.id, filter_obj.name, user_id)
                        
                        # Forward to user
                        await self._forward_post(message, real_estate_ad, filter_id, filter_obj.name, user_id)
                    else:
                        logger.info("Ad %s does not match filter '%s' for user %s", message.id, filter_obj.name, user_id)
                        
                except Exception as e:
                    logger.error("Error checking filter %s for ad %s: %s", filter_doc.get("_id"), message.id, e)
                    continue
            
            # Update message status to PARSED only if not already DUPLICATE
            # (duplicates should keep their DUPLICATE status)
            existing_msg = await db.incoming_messages.find_one({"id": message.id, "channel_id": message.chat_id})
            if existing_msg and existing_msg.get("processing_status") != IncomingMessageStatus.DUPLICATE:
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {"$set": {"processing_status": IncomingMessageStatus.PARSED, "updated_at": message.date}},
                )
            
        except Exception as e:
            logger.error("Error checking filters for all users: %s", e)

    async def _forward_post(self, message: Optional[Message], real_estate_ad: Any, filter_id: str, filter_name: Optional[str] = None, target_user_id: Optional[int] = None) -> None:
        """Forward post to user via bot"""
        try:
            # Use target_user_id if provided, otherwise get primary user ID
            if target_user_id:
                user_id = target_user_id
                logger.info("Using target_user_id: %s", user_id)
            else:
                user_id = await user_service.get_primary_user_id()
                logger.info("Using primary user_id: %s", user_id)
                
            if not user_id:
                logger.warning("No user ID found, skipping notification")
                return

            # Create formatted message with filter information
            formatted_message = await self._format_real_estate_message(real_estate_ad, message, filter_id, filter_name)

            # Send to user via notification service
            # Create inline keyboard with settings button
            keyboard = [[InlineKeyboardButton("⚙️ Настроить фильтры", callback_data="open_settings")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if self.notification_service:
                logger.info("Calling notification_service.send_message for user %s", user_id)
                await self.notification_service.send_message(
                    user_id=user_id, message=formatted_message, parse_mode="MarkdownV2", reply_markup=reply_markup
                )
            else:
                logger.warning("Notification service is not available for user %s", user_id)

            # Save forwarding record
            db = mongodb.get_database()
            
            # Get channel and topic information
            channel_info = await self._get_channel_info(real_estate_ad.original_channel_id)
            topic_title = None
            if real_estate_ad.original_topic_id:
                topic_title = await self._get_topic_title(real_estate_ad.original_channel_id, real_estate_ad.original_topic_id)
            
            # Get ad ID (should be set after saving to MongoDB)
            ad_id = real_estate_ad.id if real_estate_ad.id else None
            if not ad_id:
                logger.warning("RealEstateAd has no id, this should not happen!")
            
            forwarding_data = {
                "message": formatted_message,  # Add formatted message
                "real_estate_ad_id": ad_id,  # Use correct ad ID
                "filter_id": filter_id,
                "user_id": user_id,  # Add user_id for backward compatibility
                "sent_to": str(user_id),  # Convert to string as per model
                "sent_to_type": "user",
                "sent_at": datetime.now(timezone.utc),
                "status": OutgoingPostStatus.SENT.value,  # Set status to SENT
                "channel_id": real_estate_ad.original_channel_id,
                "channel_title": channel_info.get("title") if channel_info else None,
                "topic_id": real_estate_ad.original_topic_id,
                "topic_title": topic_title,
                "incoming_message_id": message.id if message else None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            await db.outgoing_posts.insert_one(forwarding_data)

            # Update RealEstateAd status to FORWARDED to prevent duplicate forwards
            if ad_id:
                await db.real_estate_ads.update_one(
                    {"_id": ObjectId(ad_id)},
                    {
                        "$set": {
                            "processing_status": RealEstateAdStatus.FORWARDED.value,
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )
                logger.info("Updated RealEstateAd %s status to FORWARDED", ad_id)

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

    async def reprocess_recent_messages(self, num_messages: int, force: bool = False, user_id: Optional[int] = None, channel_id: Optional[int] = None, stop_on_existing: bool = False) -> dict:
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

        # Get monitored channels - use new system
        if channel_id:
            # Specific channel requested
            channels = [channel_id]
            logger.info("Using specific channel: %s", channel_id)
        else:
            # Use new monitored channels system
            monitored_channels = await self._get_monitored_channels_new()
            channels = [c["channel_id"] for c in monitored_channels]
            logger.info("Using monitored channels: %s", channels)
            
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
            
            # Process all messages from the channel
            async for message in self.client.iter_messages(int(channel_id), limit=messages_to_fetch):
                messages.append(message)

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
                
                # If stop_on_existing is True and message exists, stop processing
                if stop_on_existing and not force:
                    logger.info("Found existing message %s, stopping processing (stop_on_existing=True)", main_message.id)
                    break

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
        """Generate Yandex Maps link for address (street + house + city only, no district)"""
        if not address:
            return None
        
        try:
            # Clean and prepare address for URL encoding
            clean_address = address.strip()
            
            # Skip district - it often confuses the map
            # Only add city if provided and not already present
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
        self, real_estate_ad: Any, _original_message: Optional[Message], filter_id: Optional[str] = None, filter_name: Optional[str] = None
    ) -> str:
        """Format real estate ad for forwarding"""
        # Get channel info for the header
        channel_info = await self._get_channel_info(real_estate_ad.original_channel_id)
        channel_title = "Неизвестного канала"
        channel_link = ""

        if channel_info:
            channel_title = self._escape_markdown(channel_info.get('title', 'Неизвестного канала'))
            if channel_info.get('username'):
                username = channel_info['username'].lstrip('@')
                channel_link = f" \\(@{self._escape_markdown(username)}\\)"

        message = f"🏠 *Найдено подходящее объявление из канала {channel_title}{channel_link}\\!*\n\n"

        if real_estate_ad.property_type:
            property_name = self._get_property_type_name(real_estate_ad.property_type)
            message += f"*Тип:* {self._escape_markdown(property_name)}\n"
        if real_estate_ad.rooms_count:
            message += f"*Комнат:* {self._escape_markdown(str(real_estate_ad.rooms_count))}\n"
        if real_estate_ad.area_sqm:
            message += f"*Площадь:* {self._escape_markdown(str(real_estate_ad.area_sqm))} кв\\.м\n"
        if real_estate_ad.price:
            # Get currency value (handle both enum and string)
            currency_value = real_estate_ad.currency.value if hasattr(real_estate_ad.currency, 'value') else str(real_estate_ad.currency)
            # Default to AMD (драм) if currency is AMD
            currency_symbol = "драм" if currency_value == "AMD" else currency_value
            message += f"*Цена:* {self._escape_markdown(f'{real_estate_ad.price:,} {currency_symbol}')}\n"
        if real_estate_ad.district:
            message += f"*Район:* {self._escape_markdown(real_estate_ad.district)}\n"
        if real_estate_ad.city:
            message += f"*Город:* {self._escape_markdown(real_estate_ad.city)}\n"
        if real_estate_ad.address:
            # Add Yandex Maps link for address
            yandex_maps_link = self._get_yandex_maps_link(real_estate_ad.address, real_estate_ad.district, real_estate_ad.city)
            if yandex_maps_link:
                # Make address clickable with Yandex Maps link
                message += f"*Адрес:* [{self._escape_markdown(real_estate_ad.address)}]({yandex_maps_link})\n"
                message += f"🗺️ [Посмотреть на карте]({yandex_maps_link})\n"
            else:
                # Fallback to plain text if no map link
                message += f"*Адрес:* {self._escape_markdown(real_estate_ad.address)}\n"
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
                # Escape underscores in username for MarkdownV2
                escaped_username = username.replace('_', '\\_')
                message += f" \\(@{escaped_username}\\)"
            
            # Add topic information if available
            if real_estate_ad.original_topic_id:
                topic_title = await self._get_topic_title(real_estate_ad.original_channel_id, real_estate_ad.original_topic_id)
                if topic_title:
                    message += f"\n*📌 Топик:* {self._escape_markdown(topic_title)}"
                else:
                    message += f"\n*📌 Топик:* #{real_estate_ad.original_topic_id}"

        # Add filter matching information
        # Note: Filter matching info is now handled via UserFilterMatch model
        if filter_name:
            message += f"\n*🎯 Активный фильтр:* {self._escape_markdown(filter_name)}\n"
        elif filter_id and filter_id != "unknown":
            # Fallback to getting filter name by ID
            filter_name = await self._get_filter_name(str(filter_id))
            message += f"\n*🎯 Активный фильтр:* {self._escape_markdown(filter_name)}\n"

        message += f"\n*Уверенность:* {self._escape_markdown(f'{real_estate_ad.parsing_confidence:.2f}')}\n"

        # Add original message link
        # If _original_message is provided (for duplicates), use its ID for the link
        # Otherwise use the ID from real_estate_ad
        if _original_message:
            message_link = self._get_message_link(
                _original_message.chat_id, _original_message.id, real_estate_ad.original_topic_id
            )
        else:
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
            
            logger.info("Topic check for message %s: top_msg=%s, reply_to_msg_id=%s, is_top_message=%s, is_reply_to_top=%s, result=%s", 
                       message.id, top_msg, reply_to_msg_id, is_top_message, is_reply_to_top, result)
            
            return result
            
        except Exception as e:
            logger.error("Error checking if message %s is in topic %s: %s", message.id, topic_id, e)
            return False

    async def refilter_ads(self, count: int, user_id: Optional[int] = None) -> dict:
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
                filter_user_id = filter_doc.get("user_id")
                if filter_user_id not in user_filters:
                    user_filters[filter_user_id] = []
                user_filters[filter_user_id].append(filter_doc)
            
            logger.info("Found filters for %s users", len(user_filters))

            # If specific user_id is provided, filter only for that user
            if user_id is not None:
                if user_id in user_filters:
                    user_filters = {user_id: user_filters[user_id]}
                    logger.info("Filtering only for user %s", user_id)
                else:
                    logger.warning("No filters found for user %s", user_id)
                    return {
                        "total_checked": len(ads_list),
                        "matched_filters": 0,
                        "forwarded": 0,
                        "errors": 0,
                        "message": f"No active filters found for user {user_id}",
                    }

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
                    
                    # Skip ads that have already been forwarded
                    if ad.processing_status == RealEstateAdStatus.FORWARDED:
                        logger.info("Skipping ad %s - already forwarded", ad.original_post_id)
                        continue

                    # Check against all users' filters using centralized service (DRY principle)
                    for user_id, user_filter_docs in user_filters.items():
                        try:
                            # Use centralized filter checking service instead of duplicating logic
                            filter_result = await filter_service.check_filters(ad, user_id)
                            
                            matching_filters = filter_result.get("matching_filters", [])
                            filter_details = filter_result.get("filter_details", {})
                            
                            logger.info("Ad %s (rooms=%s, price=%s %s) checked against user %s filters: %d matches", 
                                       ad.original_post_id, ad.rooms_count, ad.price, ad.currency, user_id, len(matching_filters))
                        
                            # Forward to user using the first matching filter
                            if matching_filters:
                                first_filter_id = matching_filters[0]
                                filter_name = filter_details.get(first_filter_id, {}).get("name", "unknown")
                                
                                await self._forward_post(None, ad, first_filter_id, filter_name, user_id)
                                forwarded += 1
                                logger.info("Ad %s forwarded to user %s with filter %s", 
                                           ad.original_post_id, user_id, filter_name)
                            else:
                                logger.info("Ad %s did not match any filters for user %s", 
                                           ad.original_post_id, user_id)
                                    
                        except Exception as e:
                            logger.error("Error checking filters for ad %s, user %s: %s", ad.original_post_id, user_id, e)
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
