import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

from telethon import TelegramClient, events, functions, types
from telethon.tl.types import Message

from app.core.config import settings
from app.db.mongodb import mongodb
from app.models.status_enums import IncomingMessageStatus
from app.services.admin_notification_service import admin_notification_service

logger = logging.getLogger(__name__)

# Type alias for the message processing callback
MessageCallback = Callable[[Message], Coroutine[Any, Any, None]]


class TelegramClientManager:
    """Manages Telethon client lifecycle, connection health, channel monitoring, and topic cache."""

    def __init__(self) -> None:
        self.client: Optional[TelegramClient] = None
        self.is_monitoring = False
        self._initialized = False
        # Cache for topic top_message IDs to reduce API calls
        self.topic_cache: Dict[tuple[int, int], int] = {}
        # Store active handlers for cleanup
        self._active_handlers: List[Any] = []
        # Store current user channels for handlers
        self._current_user_channels: Dict[int, List[Dict]] = {}
        # Retry logic for connection errors
        self._retry_attempts = 0
        self._max_retries = 3
        self._last_retry_time: Optional[datetime] = None
        self._connection_healthy = True
        # Callbacks set by facade
        self._process_message_callback: Optional[MessageCallback] = None
        self._reprocess_stuck_callback: Optional[Callable] = None
        # Notification service for admin alerts on connection failure
        self.notification_service: Any = None

    def set_callbacks(
        self,
        process_message: MessageCallback,
        reprocess_stuck: Callable,
    ) -> None:
        """Set callbacks for message processing (wired by facade)."""
        self._process_message_callback = process_message
        self._reprocess_stuck_callback = reprocess_stuck

    # ------------------------------------------------------------------
    # Connection health & retry
    # ------------------------------------------------------------------

    async def _handle_connection_error(self, error: Exception) -> bool:
        self._retry_attempts += 1
        self._connection_healthy = False
        delay = min(2 ** (self._retry_attempts - 1), 60)

        logger.error(
            "Connection error in TelegramService (attempt %d/%d): %s",
            self._retry_attempts, self._max_retries, error,
            extra={
                "error_type": type(error).__name__,
                "retry_attempt": self._retry_attempts,
                "max_retries": self._max_retries,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

        if self._retry_attempts <= self._max_retries:
            logger.info("Retrying connection in %d seconds...", delay)
            self._last_retry_time = datetime.now(timezone.utc)
            await asyncio.sleep(delay)
            return True
        else:
            logger.error("Max retry attempts (%d) exceeded for connection error", self._max_retries)
            await self._notify_admins_connection_failed(error)
            return False

    async def _notify_admins_connection_failed(self, error: Exception) -> None:
        if not self.notification_service:
            logger.warning("No notification service available for admin notification")
            return
        try:
            error_details = f"{type(error).__name__}: {str(error)}"
            await admin_notification_service.notify_service_restart(
                attempt=self._retry_attempts,
                error=error_details,
                will_retry=False
            )
            logger.info("Admin notification sent for connection failure")
        except Exception as e:
            logger.error("Failed to send admin notification: %s", e)

    def _reset_retry_state(self) -> None:
        self._retry_attempts = 0
        self._last_retry_time = None
        self._connection_healthy = True
        logger.info("Connection retry state reset - connection is healthy")

    def is_connection_healthy(self) -> bool:
        if not self.client:
            return False
        return self._connection_healthy and self.client.is_connected()

    def get_connection_status(self) -> Dict[str, Any]:
        return {
            "is_connected": self.client.is_connected() if self.client else False,
            "is_monitoring": self.is_monitoring,
            "is_healthy": self._connection_healthy,
            "retry_attempts": self._retry_attempts,
            "max_retries": self._max_retries,
            "last_retry_time": self._last_retry_time.isoformat() if self._last_retry_time else None,
            "initialized": self._initialized
        }

    # ------------------------------------------------------------------
    # Topic cache
    # ------------------------------------------------------------------

    async def _initialize_topic_cache(self) -> None:
        if not self.client:
            logger.warning("Telegram client not available for topic cache initialization")
            return
        try:
            db = mongodb.get_database()
            monitored_channels = await db.monitored_channels.find({
                "is_active": True,
                "topic_id": {"$ne": None}
            }).to_list(length=None)

            unique_combinations = set()
            for channel in monitored_channels:
                channel_id = channel.get("channel_id")
                topic_id = channel.get("topic_id")
                if channel_id and topic_id:
                    if isinstance(channel_id, str):
                        try:
                            channel_id = int(channel_id)
                        except ValueError:
                            continue
                    unique_combinations.add((channel_id, topic_id))

            logger.info("Initializing topic cache for %d unique channel-topic combinations", len(unique_combinations))

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
        if not self.client:
            logger.warning("Telegram client not available for topic cache update")
            return
        try:
            if isinstance(channel_id, str):
                try:
                    channel_id = int(channel_id)
                except ValueError:
                    logger.error("Invalid channel_id format: %s", channel_id)
                    return

            cache_key = (channel_id, topic_id)
            if cache_key in self.topic_cache:
                return

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
        """Public method to update topic cache when new subscriptions are added."""
        await self._update_topic_cache(channel_id, topic_id)

    async def _get_top_message_for_topic(self, channel_id: int, topic_id: int) -> Optional[int]:
        try:
            if not self.client:
                return None
            cache_key = (channel_id, topic_id)
            if cache_key in self.topic_cache:
                return self.topic_cache[cache_key]

            if channel_id < 0:
                regular_id = abs(channel_id) - 1000000000000
            else:
                regular_id = channel_id

            channel = await self.client.get_input_entity(regular_id)
            result: types.messages.ForumTopics = await self.client(
                functions.channels.GetForumTopicsByIDRequest(channel=channel, topics=[topic_id])
            )

            if not result.topics:
                logger.error("No such topic_id=%s in channel %s", topic_id, channel_id)
                return None

            top_message = result.topics[0].top_message
            self.topic_cache[cache_key] = top_message
            return top_message
        except Exception as e:
            logger.error("Error getting top message for channel %s, topic %s: %s", channel_id, topic_id, e)
            return None

    async def _iter_topic_messages(self, channel_id: int, topic_id: int, limit: Optional[int] = None):
        try:
            if not self.client:
                return
            top_msg = await self._get_top_message_for_topic(channel_id, topic_id)
            if not top_msg:
                logger.error("Could not get top message for topic %s in channel %s", topic_id, channel_id)
                return
            async for msg in self.client.iter_messages(channel_id, reply_to=top_msg, limit=limit):
                yield msg
        except Exception as e:
            logger.error("Error iterating topic messages for channel %s, topic %s: %s", channel_id, topic_id, e)

    async def _is_message_in_topic(self, message, channel_id: int, topic_id: int) -> bool:
        try:
            if not self.client:
                return False
            cache_key = (channel_id, topic_id)
            top_msg = self.topic_cache.get(cache_key)

            if top_msg is None:
                top_msg = await self._get_top_message_for_topic(channel_id, topic_id)
                if top_msg:
                    self.topic_cache[cache_key] = top_msg
                else:
                    logger.warning("Could not get top message for topic %s in channel %s", topic_id, channel_id)
                    return False

            rt = getattr(message, "reply_to", None)
            reply_to_msg_id = getattr(rt, "reply_to_msg_id", None) if rt else None
            is_top_message = message.id == top_msg
            is_reply_to_top = reply_to_msg_id == top_msg
            result = is_top_message or is_reply_to_top

            logger.info(
                "Topic check for message %s: top_msg=%s, reply_to_msg_id=%s, is_top_message=%s, is_reply_to_top=%s, result=%s",
                message.id, top_msg, reply_to_msg_id, is_top_message, is_reply_to_top, result
            )
            return result
        except Exception as e:
            logger.error("Error checking if message %s is in topic %s: %s", message.id, topic_id, e)
            return False

    # ------------------------------------------------------------------
    # Monitoring lifecycle
    # ------------------------------------------------------------------

    async def start_monitoring(self) -> None:
        if self.is_monitoring:
            logger.warning("Monitoring is already active")
            return

        while True:
            try:
                if not self.client or not self._initialized:
                    if self.client:
                        try:
                            await self.client.disconnect()
                        except Exception:
                            pass
                    self.client = TelegramClient(
                        settings.TELEGRAM_SESSION_NAME, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH
                    )
                    await self.client.start(phone=settings.TELEGRAM_PHONE)
                    self._initialized = True
                    logger.info("Telegram client initialized successfully")
                elif not self.client.is_connected():
                    await self.client.start(phone=settings.TELEGRAM_PHONE)
                    logger.info("Telegram client reconnected")

                self._reset_retry_state()

                monitored_channels = await self._get_monitored_channels_new()
                if not monitored_channels:
                    logger.warning("No monitored channels found")
                    return

                logger.info("Monitoring %d channels: %s", len(monitored_channels), [c["channel_id"] for c in monitored_channels])
                await self._register_monitored_channel_handlers(monitored_channels)

                self.is_monitoring = True
                logger.info("Started monitoring Telegram channels")

                logger.info("Starting Telegram client in background...")
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

                async def run_client():
                    try:
                        logger.info("Telegram client background task started")
                        await self.client.run_until_disconnected()
                        logger.info("Telegram client disconnected")
                    except Exception as e:
                        logger.error("Error in Telegram client background task: %s", e)
                        if isinstance(e, (ConnectionError, TimeoutError, OSError)):
                            await self._handle_connection_error(e)

                asyncio.create_task(run_client())
                logger.info("Telegram client background task created")

                await self._load_recent_messages_from_monitored_channels(monitored_channels, settings.STARTUP_MESSAGE_LIMIT)

                if self._reprocess_stuck_callback:
                    await self._reprocess_stuck_callback()

                break

            except (ConnectionError, TimeoutError, OSError) as e:
                will_retry = await self._handle_connection_error(e)
                if not will_retry:
                    logger.error("Max retry attempts exceeded, giving up on monitoring. Exiting to trigger container restart.")
                    sys.exit(1)
                continue
            except Exception as e:
                logger.error("Error starting monitoring: %s", e)
                raise

    async def _get_monitored_channels_new(self) -> List[Dict]:
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
        try:
            channel_ids = [c["channel_id"] for c in monitored_channels]
            if not channel_ids:
                logger.warning("No channel IDs to register handlers for")
                return

            logger.info("Registering handlers for %d channels: %s", len(channel_ids), channel_ids)

            @self.client.on(events.NewMessage(chats=channel_ids))
            async def handle_new_message(event: events.NewMessage.Event) -> None:
                try:
                    message = event.message
                    if self._process_message_callback:
                        await self._process_message_callback(message)
                except Exception as e:
                    logger.error("Error handling new message: %s", e)

            logger.info("Registered handlers for monitored channels")
        except Exception as e:
            logger.error("Error registering monitored channel handlers: %s", e)

    async def _load_recent_messages_from_monitored_channels(self, monitored_channels: List[Dict], limit: int = 100) -> None:
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

                    async for message in self.client.iter_messages(channel_id, limit=limit):
                        total_messages += 1
                        try:
                            db = mongodb.get_database()
                            existing_post = await db.incoming_messages.find_one({
                                "id": message.id, "channel_id": message.chat_id
                            })

                            if existing_post:
                                current_status = existing_post.get("processing_status")
                                if current_status == IncomingMessageStatus.DELETED:
                                    logger.debug("Skipping message %s - status is DELETED", message.id)
                                    skipped_messages += 1
                                    channel_skipped += 1
                                    continue

                                if current_status in [IncomingMessageStatus.PARSED, IncomingMessageStatus.NOT_REAL_ESTATE, IncomingMessageStatus.SPAM_FILTERED, IncomingMessageStatus.MEDIA_ONLY]:
                                    processing_count = await db.incoming_messages.count_documents({
                                        "channel_id": message.chat_id,
                                        "processing_status": IncomingMessageStatus.PROCESSING
                                    })
                                    if processing_count > 0:
                                        logger.info("Found already processed message %s, but %d messages in PROCESSING status, continuing catch-up",
                                                    message.id, processing_count)
                                        skipped_messages += 1
                                        channel_skipped += 1
                                        continue
                                    else:
                                        logger.info("Found already processed message %s in channel %s, stopping catch-up for this channel", message.id, channel_id)
                                        skipped_messages += 1
                                        channel_skipped += 1
                                        break
                                elif current_status == IncomingMessageStatus.ERROR:
                                    from app.services.llm_quota_service import llm_quota_service
                                    parsing_errors = existing_post.get("parsing_errors", [])
                                    is_quota_error = any(
                                        "quota" in str(error).lower() or "insufficient" in str(error).lower()
                                        for error in parsing_errors
                                    )
                                    if is_quota_error and llm_quota_service.is_quota_exceeded():
                                        logger.info("Skipping message %s with quota error status (quota still exceeded)", message.id)
                                        skipped_messages += 1
                                        channel_skipped += 1
                                        continue
                                    logger.info("Message %s had error status, reprocessing", message.id)
                                    if self._process_message_callback:
                                        await self._process_message_callback(message)
                                    processed_messages += 1
                                    channel_processed += 1
                                elif current_status == IncomingMessageStatus.PROCESSING:
                                    logger.info("Message %s has PROCESSING status, reprocessing (was interrupted)", message.id)
                                    if self._process_message_callback:
                                        await self._process_message_callback(message)
                                    processed_messages += 1
                                    channel_processed += 1
                                else:
                                    logger.info("Message %s has status %s, processing", message.id, current_status)
                                    if self._process_message_callback:
                                        await self._process_message_callback(message)
                                    processed_messages += 1
                                    channel_processed += 1
                            else:
                                if self._process_message_callback:
                                    await self._process_message_callback(message)
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
        try:
            logger.info("Loading recent messages from %d channels (limit: %d)", len(user_channels), limit)
            total_loaded = 0
            total_processed = 0
            total_messages_found = 0

            for channel_id, subscriptions in user_channels.items():
                try:
                    logger.info("Loading messages from channel %s", channel_id)
                    channel_entity = await self.client.get_entity(channel_id)
                    messages = await self.client.get_messages(channel_entity, limit=limit)
                    logger.info("Found %d messages in channel %s", len(messages), channel_id)
                    total_messages_found += len(messages)

                    for message in messages:
                        db = mongodb.get_database()
                        existing_message = await db.incoming_messages.find_one({
                            "id": message.id, "channel_id": message.chat_id
                        })
                        if existing_message:
                            logger.info("Message %s already exists in database, stopping processing (stop_on_existing=True)", message.id)
                            break

                        for subscription in subscriptions:
                            user_id = subscription["user_id"]
                            topic_id = subscription["topic_id"]
                            monitor_all_topics = subscription["monitor_all_topics"]
                            monitored_topics = subscription["monitored_topics"]

                            should_process = False
                            if monitor_all_topics:
                                should_process = True
                            elif topic_id and monitored_topics:
                                if topic_id in monitored_topics:
                                    should_process = True
                            elif topic_id:
                                if await self._is_message_in_topic(message, channel_id, topic_id):
                                    should_process = True
                            else:
                                should_process = True

                            if should_process and self._process_message_callback:
                                await self._process_message_callback(message)
                                total_processed += 1

                        total_loaded += 1

                except Exception as e:
                    logger.error("Error loading messages from channel %s: %s", channel_id, e)
                    continue

            logger.info("Found %d total messages, loaded %d text messages, processed %d", total_messages_found, total_loaded, total_processed)
        except Exception as e:
            logger.error("Error loading recent messages: %s", e)

    async def _register_channel_handlers(self, user_channels: Dict[int, List[Dict]]) -> None:
        try:
            await self._clear_handlers()
            channel_ids = list(user_channels.keys())
            logger.info("Registering handlers for channels: %s", channel_ids)
            self._current_user_channels = user_channels

            for channel_id in channel_ids:
                @self.client.on(events.NewMessage(chats=[channel_id]))
                async def handle_new_message_user(event: events.NewMessage.Event) -> None:
                    if self._process_message_callback:
                        await self._process_message_callback(event.message)

                self._active_handlers.append(handle_new_message_user)

            logger.info("Registered separate handlers for %d channels", len(channel_ids))
        except Exception as e:
            logger.error("Error registering channel handlers: %s", e)
            raise

    async def _clear_handlers(self) -> None:
        try:
            self._active_handlers.clear()
            logger.info("Cleared all event handlers")
        except Exception as e:
            logger.error("Error clearing handlers: %s", e)

    async def update_channel_monitoring(self) -> None:
        try:
            if not self.is_monitoring:
                logger.warning("Monitoring not active, cannot update channels")
                return
            monitored_channels = await self._get_monitored_channels_new()
            if not monitored_channels:
                logger.warning("No monitored channels found for monitoring update")
                return
            await self._register_monitored_channel_handlers(monitored_channels)
            logger.info("Updated channel monitoring with %d channels", len(monitored_channels))
        except Exception as e:
            logger.error("Error updating channel monitoring: %s", e)

    async def _get_monitored_channel_id_by_telegram_id(self, telegram_channel_id: int) -> Optional[str]:
        try:
            db = mongodb.get_database()
            if db is None:
                return None
            channel_id_str = str(telegram_channel_id)
            if channel_id_str.startswith('-100'):
                channel_id_str = channel_id_str[4:]
            channel_doc = await db.monitored_channels.find_one({
                "channel_id": channel_id_str, "is_active": True
            })
            if channel_doc:
                return str(channel_doc["_id"])
            return None
        except Exception as e:
            logger.error("Error getting monitored channel ID: %s", e)
            return None

    async def stop_monitoring(self) -> None:
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
        except Exception as e:
            logger.error("Error stopping monitoring: %s", e)
            raise

    async def analyze_channel_structure(self, channel_id: int, limit: int = 50) -> Optional[Dict[str, Any]]:
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

                if len(sample_messages) < 10:
                    sample_messages.append({
                        "id": message.id,
                        "text": message.text[:100] if message.text else "No text",
                        "reply_to": message.reply_to,
                        "reply_to_top_id": (
                            getattr(message.reply_to, "reply_to_top_id", None) if message.reply_to else None
                        ),
                        "date": message.date,
                    })

            logger.info("Channel %s analysis results:", channel_id)
            logger.info("Messages without topic (main channel): %s", no_topic_count)
            for tid, count in topic_stats.items():
                logger.info("  Topic %s: %s messages", tid, count)

            return {
                "channel_id": channel_id,
                "no_topic_count": no_topic_count,
                "topic_stats": topic_stats,
                "sample_messages": sample_messages,
            }
        except Exception as e:
            logger.error("Error analyzing channel structure: %s", e)
            return None

    async def get_status(self) -> Dict[str, Any]:
        return {
            "is_monitoring": self.is_monitoring,
            "is_connected": (self.client and self.client.is_connected() if self.client else False),
        }
