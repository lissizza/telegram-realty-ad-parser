import logging
from typing import List, Optional

from telethon import TelegramClient, events
from telethon.tl.types import Message

from app.core.config import settings
from app.services.parser_service import ParserService
from app.services.llm_service import LLMService
from app.services.simple_filter_service import SimpleFilterService
# SpamFilter removed - using LLM for spam detection instead
# MessageStatus removed - using processing_status strings instead
from app.db.mongodb import mongodb

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.parser_service = ParserService()
        self.llm_service = LLMService()
        self.simple_filter_service = SimpleFilterService()
        # SpamFilter removed - using LLM for spam detection
        self.is_monitoring = False

    async def start_monitoring(self):
        """Start monitoring Telegram channels"""
        if self.is_monitoring:
            logger.warning("Monitoring is already active")
            return

        try:
            # Initialize Telegram client
            self.client = TelegramClient(
                settings.TELEGRAM_SESSION_NAME,
                settings.TELEGRAM_API_ID,
                settings.TELEGRAM_API_HASH
            )

            await self.client.start(phone=settings.TELEGRAM_PHONE)

            # Register event handlers for channels
            monitored_channels = self._get_monitored_channels()
            monitored_subchannels = self._get_monitored_subchannels()
            
            if monitored_channels:
                @self.client.on(
                    events.NewMessage(chats=monitored_channels)
                )
                async def handle_new_message(event: events.NewMessage.Event):
                    # Process only messages from main topic (reply_to_msg_id=2629)
                    # Skip all other subchannels
                    message = event.message
                    rt = getattr(message, "reply_to", None)
                    reply_to_msg_id = getattr(rt, "reply_to_msg_id", None) if rt else None
                    
                    logger.info(f"Message {message.id}: reply_to={rt}, reply_to_msg_id={reply_to_msg_id}")
                    
                    if rt and reply_to_msg_id == 2629:
                        # Message from main topic with real estate ads, process it
                        logger.info(f"Message {message.id} from main topic (reply_to_msg_id=2629), processing")
                    else:
                        # Message from other subchannels or no reply_to, skip it
                        logger.info(f"Message {message.id} from subchannel {reply_to_msg_id} or no reply_to, skipping")
                        return
                    await self._process_message(event.message)

            self.is_monitoring = True
            logger.info("Started monitoring Telegram channels")

            # Keep the client running
            await self.client.run_until_disconnected()

        except Exception as e:
            logger.error(f"Error starting monitoring: {e}")
            raise

    async def stop_monitoring(self):
        """Stop monitoring Telegram channels"""
        if not self.is_monitoring:
            logger.warning("Monitoring is not active")
            return

        try:
            if self.client:
                await self.client.disconnect()
            self.is_monitoring = False
            logger.info("Stopped monitoring Telegram channels")
        except Exception as e:
            logger.error(f"Error stopping monitoring: {e}")
            raise

    async def analyze_channel_structure(self, channel_id: int, limit: int = 50):
        """Analyze channel structure to understand topics"""
        logger.info(f"Analyzing channel structure for channel {channel_id}")
        topic_stats = {}
        no_topic_count = 0
        sample_messages = []
        
        try:
            async for message in self.client.iter_messages(channel_id, limit=limit):
                if message.reply_to and hasattr(message.reply_to, 'reply_to_top_id'):
                    topic_id = message.reply_to.reply_to_top_id
                    if topic_id not in topic_stats:
                        topic_stats[topic_id] = 0
                    topic_stats[topic_id] += 1
                else:
                    no_topic_count += 1
                
                # Collect sample messages for analysis
                if len(sample_messages) < 10:
                    sample_messages.append({
                        'id': message.id,
                        'text': message.text[:100] if message.text else 'No text',
                        'reply_to': message.reply_to,
                        'reply_to_top_id': getattr(message.reply_to, 'reply_to_top_id', None) if message.reply_to else None,
                        'date': message.date
                    })
            
            # Log results
            logger.info(f"Channel {channel_id} analysis results:")
            logger.info(f"Messages without topic (main channel): {no_topic_count}")
            logger.info("Topics and message counts:")
            for topic_id, count in topic_stats.items():
                logger.info(f"  Topic {topic_id}: {count} messages")
            
            logger.info("Sample messages:")
            for msg in sample_messages:
                logger.info(f"  Message ID: {msg['id']}")
                logger.info(f"  Text: {msg['text']}...")
                logger.info(f"  Reply to: {msg['reply_to']}")
                logger.info(f"  Reply to top ID: {msg['reply_to_top_id']}")
                logger.info(f"  Date: {msg['date']}")
                logger.info("-" * 50)
            
            return {
                'channel_id': channel_id,
                'no_topic_count': no_topic_count,
                'topic_stats': topic_stats,
                'sample_messages': sample_messages
            }
            
        except Exception as e:
            logger.error(f"Error analyzing channel structure: {e}")
            return None

    async def get_status(self):
        """Get bot status"""
        return {
            "is_monitoring": self.is_monitoring,
            "is_connected": (
                self.client and self.client.is_connected() 
                if self.client else False
            )
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
            channel_ids = []
            for channel_id in channel_strings:
                channel_id = channel_id.strip()
                if not channel_id:
                    continue
                try:
                    # Handle both @username and numeric IDs
                    if channel_id.startswith('@'):
                        # For @username, we need to resolve it to numeric ID
                        # This will be handled by Telethon automatically
                        channel_ids.append(channel_id)
                    else:
                        # Convert numeric string to int
                        channel_ids.append(int(channel_id))
                except ValueError as e:
                    logger.warning(f"Invalid channel ID format: {channel_id} - {e}")
                    continue
            
            if not channel_ids:
                logger.warning("No valid monitored channels found")
                return []
            
            logger.info(
                f"Monitoring {len(channel_ids)} channels: {channel_ids}"
            )
            return channel_ids
        except Exception as e:
            logger.error(f"Error getting monitored channels: {e}")
            return []
    
    def _get_monitored_subchannels(self) -> List[tuple]:
        """Get list of monitored subchannel (topic) IDs from settings"""
        try:
            subchannels = settings.monitored_subchannels_list
            
            if not subchannels:
                logger.info("No monitored subchannels configured")
                return []
            
            logger.info(
                f"Monitoring {len(subchannels)} subchannels: {subchannels}"
            )
            return subchannels
        except Exception as e:
            logger.error(f"Error getting monitored subchannels: {e}")
            return []
    
    def _is_message_in_topic(self, message: Message, topic_id: int) -> bool:
        """Check if message is in the specified topic (old method - kept for compatibility)"""
        try:
            # Check if message is in the specific topic
            if message.reply_to and hasattr(message.reply_to, 'reply_to_top_id'):
                if message.reply_to.reply_to_top_id == topic_id:
                    logger.debug(f"Message {message.id} is in topic {topic_id} (via reply_to)")
                    return True
            
            # For messages without reply_to, we cannot determine the topic
            # This is a limitation of Telegram API - we need reply_to to identify topics
            # We'll be strict and only process messages with reply_to
            logger.debug(f"Message {message.id} has no reply_to, cannot determine topic, skipping")
            return False
            
        except Exception as e:
            logger.error(f"Error checking topic: {e}")
            return False

    def _is_message_in_topic_correct(self, message: Message, topic_id: int) -> bool:
        """Check if message is in the main topic (no reply_to) - where real estate ads are posted"""
        try:
            # We want messages from the main topic (no reply_to)
            # Real estate ads are posted in the main topic, not in sub-topics
            rt = getattr(message, "reply_to", None)
            if rt:
                reply_to_top_id = getattr(rt, "reply_to_top_id", None)
                logger.debug(f"Message {message.id}: reply_to_top_id={reply_to_top_id} (sub-topic, skipping)")
                return False
            else:
                logger.debug(f"Message {message.id}: no reply_to (main topic, processing)")
                return True
            
        except Exception as e:
            logger.error(f"Error checking topic: {e}")
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
            for channel_id, topic_id in monitored_subchannels:
                if message.chat_id == channel_id:
                    logger.debug(f"Message {message.id} from channel {channel_id}, processing (already filtered by topic)")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking subchannel: {e}")
            return False
    
    def _is_media_only_message(self, message: Message) -> bool:
        """Check if message contains only media without text"""
        try:
            # Check if message has text
            if message.text and message.text.strip():
                return False
            
            # Check if message has media
            has_media = (
                message.photo or 
                message.video or 
                message.document or 
                message.audio or 
                message.voice or 
                message.video_note or 
                message.sticker or 
                message.animation or 
                message.contact or 
                message.location or 
                message.venue or 
                message.poll or 
                message.game or 
                message.web_preview
            )
            
            return has_media
        except Exception as e:
            logger.error(f"Error checking media-only message: {e}")
            return False
    
    async def _save_message_status(self, message: Message, status: str):
        """Save message with specific status using IncomingMessage model"""
        try:
            from app.models.incoming_message import IncomingMessage
            from datetime import datetime
            
            db = mongodb.get_database()
            message_text = message.text or ""
            
            # Get channel title
            channel_title = "Unknown Channel"
            try:
                channel = await self.client.get_entity(message.chat_id)
                channel_title = getattr(channel, 'title', 'Unknown Channel')
            except:
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
                forwarded_to=None
            )
            
            # Convert to dict for MongoDB
            message_data = incoming_message.model_dump(exclude={"id"})
            
            await db.incoming_messages.update_one(
                {"id": message.id, "channel_id": message.chat_id},
                {"$set": message_data},
                upsert=True
            )
            
            logger.info(f"Saved message {message.id} with status {status}")
        except Exception as e:
            logger.error(f"Error saving message status: {e}")

    async def _process_message(self, message: Message, force: bool = False):
        """Process incoming message"""
        real_estate_ad = None  # Initialize variable
        logger.info(f"DEBUG: _process_message called for message {message.id}")
        logger.info(f"DEBUG: Message type: {type(message)}")
        logger.info(f"DEBUG: Message chat_id: {message.chat_id}")
        logger.info(f"DEBUG: Message text: {message.text[:100] if message.text else 'None'}")
        logger.info(f"DEBUG: About to enter try block")
        try:
            # Check if message is from monitored subchannel (topic)
            if not self._is_from_monitored_subchannel(message):
                logger.debug(f"Message {message.id} not from monitored subchannel, skipping")
                return
            else:
                logger.debug(f"Message {message.id} is from monitored subchannel, continuing")
            
            # Check if message is media-only (skip processing completely)
            if self._is_media_only_message(message):
                logger.debug(f"Message {message.id} is media-only, skipping completely")
                return
            else:
                logger.debug(f"Message {message.id} is not media-only, continuing")
            # Check if message already processed
            db = mongodb.get_database()
            existing_post = await db.incoming_messages.find_one({
                "id": message.id,
                "channel_id": message.chat_id
            })
            
            if existing_post:
                # Check if we need to reprocess (e.g., if status is ERROR or force=True)
                if not force and existing_post.get("processing_status") not in ["error"]:
                    logger.debug(f"Message {message.id} already processed with status {existing_post.get('processing_status')}, skipping")
                    return
                else:
                    logger.info(f"Reprocessing message {message.id} (previous status: {existing_post.get('processing_status')})")

            # Create post data with initial status (IncomingMessage format)
            channel_title = "Unknown"
            try:
                if message.chat and hasattr(message.chat, 'title'):
                    channel_title = message.chat.title
            except Exception as e:
                logger.warning(f"Could not get channel title for message {message.id}: {e}")
            
            post_data = {
                "id": message.id,
                "channel_id": message.chat_id,
                "channel_title": channel_title,
                "message": message.text or "",
                "date": message.date,
                "views": getattr(message, 'views', None),
                "forwards": getattr(message, 'forwards', None),
                "replies": None,  # Skip replies object as it's not serializable
                "media_type": None,  # TODO: implement media detection
                "media_url": None,  # TODO: implement URL extraction
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
            
            logger.debug(f"Created post_data for message {message.id}")
            logger.debug(f"Message date type: {type(message.date)}")
            logger.debug(f"Message chat_id: {message.chat_id}")
            logger.debug(f"Message text length: {len(message.text or '')}")
            logger.debug(f"Channel title: {channel_title}")

            # Save or update IncomingMessage first
            if existing_post:
                # Update existing post
                result = await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {"$set": post_data}
                )
                logger.debug(f"Updated incoming_message for {message.id}: {result.modified_count} modified")
                incoming_message_id = str(existing_post["_id"])
            else:
                # Insert new post
                result = await db.incoming_messages.insert_one(post_data)
                logger.debug(f"Inserted incoming_message for {message.id}: {result.inserted_id}")
                incoming_message_id = str(result.inserted_id)

            # Try to parse as real estate ad using LLM
            message_text = message.text or ""
            logger.info(f"Message {message.id}: text='{message_text}', has_text={bool(message.text)}")
            
            # Skip technical bot messages
            if message_text and any(tech_indicator in message_text.lower() for tech_indicator in [
                "недостаточно прав", "блокировки", "тихий режим", "настройки бота",
                "технические особенности", "работать некорректно", "cas.chat"
            ]):
                logger.info(f"Message {message.id} is a technical bot message, skipping")
                return
            
            if message_text:
                # Skip spam filtering - LLM will handle it
                
                # Let LLM determine if it's a real estate ad
                logger.info(f"Processing message {message.id} with LLM")
                
                # Update status to parsing
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {"$set": {"processing_status": "processing", "updated_at": message.date}}
                )
                
                # Use parser service which will choose between LLM and rule-based parsing
                # Create IncomingMessage object for parsing
                from app.models.incoming_message import IncomingMessage
                
                # Get topic_id for this channel from settings
                topic_id = settings.get_topic_id_for_channel(message.chat_id)
                
                incoming_message_obj = IncomingMessage(
                    id=message.id,
                    channel_id=message.chat_id,
                    topic_id=topic_id,
                    channel_title=channel_title,
                    message=message_text,
                    date=message.date,
                    processing_status="processing"
                )
                # Set the MongoDB ID
                incoming_message_obj._id = incoming_message_id
                
                real_estate_ad = await self.parser_service.parse_real_estate_ad(incoming_message_obj)

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
                            {"original_post_id": message.id}, 
                            ad_data, 
                            upsert=True
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
                            {"$set": {
                                "processing_status": "parsed",
                                "is_real_estate": True,
                                "real_estate_confidence": real_estate_ad.parsing_confidence,
                                "real_estate_ad_id": real_estate_ad.id,
                                "updated_at": message.date
                            }}
                        )
                    else:
                        # LLM determined this is not real estate
                        await db.incoming_messages.update_one(
                            {"id": message.id, "channel_id": message.chat_id},
                            {"$set": {
                                "processing_status": "not_real_estate",
                                "is_real_estate": False,
                                "updated_at": message.date
                            }}
                        )
                    
                    # Log filter matching details
                    if filter_result["matching_filters"]:
                        logger.info(f"Ad {message.id} matches filters: {filter_result['matching_filters']}")
                        for filter_id, details in filter_result["filter_details"].items():
                            logger.info(f"Filter {filter_id} ({details['name']}): matched")
                        
                        # Update status to filtered
                        await db.incoming_messages.update_one(
                            {"id": message.id, "channel_id": message.chat_id},
                            {"$set": {"processing_status": "filtered", "updated_at": message.date}}
                        )
                    else:
                        logger.info(f"Ad {message.id} does not match any filters")

                    # Forward if matches
                    for filter_id in filter_result["matching_filters"]:
                        await self._forward_post(
                            message, real_estate_ad, filter_id
                        )

            # Mark message as processed
            if real_estate_ad:
                # Already updated above
                pass
            else:
                # LLM determined this is not a real estate ad
                logger.info(f"Message {message.id} not identified as real estate ad by LLM")
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {"$set": {
                        "processing_status": "not_real_estate",
                        "is_real_estate": False, 
                        "processed_at": message.date,
                        "updated_at": message.date
                    }}
                )

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # Update status to error
            try:
                db = mongodb.get_database()
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {"$set": {
                        "processing_status": "error",
                        "parsing_errors": [str(e)],
                        "processed_at": message.date,
                        "updated_at": message.date
                    }}
                )
            except Exception as update_error:
                logger.error(f"Error updating post status to error: {update_error}")

    async def _forward_post(self, message: Message, real_estate_ad, filter_id: str):
        """Forward post to user via bot"""
        try:
            # Get user ID from settings (your Telegram user ID)
            user_id = settings.TELEGRAM_USER_ID  # We need to add this to config
            
            if not user_id:
                logger.warning("No user ID configured for forwarding")
                return

            # Create formatted message with filter information
            formatted_message = await self._format_real_estate_message(real_estate_ad, message, filter_id)
            
            # Send to user via bot with inline keyboard
            from app.telegram_bot import telegram_bot
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            if telegram_bot.application:
                # Create inline keyboard with settings button
                keyboard = [
                    [InlineKeyboardButton("⚙️ Настроить фильтры", callback_data="open_settings")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await telegram_bot.application.bot.send_message(
                    chat_id=user_id,
                    text=formatted_message,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )

            # Save forwarding record
            db = mongodb.get_database()
            forwarding_data = {
                "original_post_id": message.id,
                "original_channel_id": message.chat_id,
                "real_estate_ad_id": real_estate_ad.id,
                "filter_id": filter_id,
                "user_id": user_id,
                "processing_status": "forwarded"
            }
            await db.forwarded_posts.insert_one(forwarding_data)

            # Update post status to forwarded
            await db.incoming_messages.update_one(
                {"id": message.id, "channel_id": message.chat_id},
                {"$set": {
                    "processing_status": "forwarded",
                    "forwarded": True,
                    "forwarded_at": message.date,
                    "forwarded_to": user_id,
                    "updated_at": message.date
                }}
            )

            logger.info(f"Forwarded post {message.id} to user {user_id} via filter {filter_id}")

        except Exception as e:
            logger.error(f"Error forwarding post: {e}")
    
    def _group_messages_by_grouped_id(self, messages):
        """Group messages by grouped_id to combine text + media messages"""
        groups = {}
        
        for message in messages:
            grouped_id = getattr(message, 'grouped_id', None)
            if grouped_id:
                if grouped_id not in groups:
                    groups[grouped_id] = []
                groups[grouped_id].append(message)
            else:
                # Messages without grouped_id are treated as individual messages
                groups[f"single_{message.id}"] = [message]
        
        # Sort messages within each group by date
        for group_id in groups:
            groups[group_id].sort(key=lambda x: x.date)
        
        return groups
    
    async def reprocess_recent_messages(self, num_messages: int, force: bool = False) -> dict:
        """Reprocess N recent messages from monitored channels"""
        logger.info(f"Starting reprocess_recent_messages: num_messages={num_messages}, force={force}")
        
        db = mongodb.get_database()
        stats = {
            'total_processed': 0,  # Number of advertisements processed
            'skipped': 0,          # Number of advertisements skipped
            'real_estate_ads': 0,  # Number of real estate advertisements found
            'spam_filtered': 0,    # Number of advertisements filtered as spam
            'not_real_estate': 0,  # Number of advertisements not about real estate
            'matched_filters': 0,  # Number of advertisements that matched user filters
            'forwarded': 0,        # Number of advertisements forwarded to user
            'errors': 0            # Number of advertisements with processing errors
        }
        
        # Get monitored channels
        channels = self._get_monitored_channels()
        if not channels:
            logger.warning("No monitored channels found")
            return stats
        
        # Get recent messages from all channels and topics
        messages_to_fetch = num_messages * 10  # Increased multiplier to get more groups
        recent_messages = []
        
        # Get monitored subchannels for topic filtering
        monitored_subchannels = self._get_monitored_subchannels()
        
        for channel_id in channels:
            # Process only messages from main topic (reply_to_msg_id=2629)
            # Skip all other subchannels
            logger.info(f"Fetching messages from channel {channel_id} (main topic only - reply_to_msg_id=2629)")
            messages = []
            async for message in self.client.iter_messages(
                int(channel_id), 
                limit=messages_to_fetch
            ):
                # Process only messages from main topic
                rt = getattr(message, "reply_to", None)
                reply_to_msg_id = getattr(rt, "reply_to_msg_id", None) if rt else None
                
                if rt and reply_to_msg_id == 2629:
                    # Message from main topic with real estate ads, process it
                    messages.append(message)
                    logger.debug(f"Message {message.id}: reply_to_msg_id={reply_to_msg_id} (main topic, processing)")
                else:
                    # Message from other subchannels or no reply_to, skip it
                    logger.debug(f"Message {message.id}: reply_to_msg_id={reply_to_msg_id} (subchannel or no reply_to, skipping)")
            
            recent_messages.extend(messages)
            logger.info(f"Fetched {len(messages)} messages from channel {channel_id} (main topic only)")
        
        # Sort by date (newest first)
        recent_messages.sort(key=lambda x: x.date, reverse=True)
        
        # Group messages by grouped_id
        grouped_messages = self._group_messages_by_grouped_id(recent_messages)
        logger.info(f"Grouped {len(recent_messages)} messages into {len(grouped_messages)} groups")
        
        # Take only the requested number of groups (newest first)
        group_items = list(grouped_messages.items())
        group_items.sort(key=lambda x: x[1][0].date, reverse=True)
        logger.info(f"Available groups: {[f'{gid} ({len(msgs)} msgs)' for gid, msgs in group_items]}")
        
        group_items = group_items[:num_messages]
        grouped_messages = dict(group_items)
        
        logger.info(f"Processing {len(grouped_messages)} advertisements (requested: {num_messages})")
        
        # Process each group of messages (advertisements)
        for group_id, group_messages in grouped_messages.items():
            logger.info(f"Processing advertisement {group_id} with {len(group_messages)} messages")
            
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
                logger.info(f"Advertisement text: {main_message.text[:200]}{'...' if len(main_message.text) > 200 else ''}")
            else:
                logger.info(f"Advertisement {group_id} has no text content")
            
            # Check if main message already exists in database
            existing_post = await db.incoming_messages.find_one({
                "id": main_message.id, 
                "channel_id": main_message.chat_id
            })
            
            if existing_post:
                current_status = existing_post.get("processing_status")
                
                if force:
                    # Force reprocessing - reset status
                    logger.info(f"Force reprocessing message {main_message.id} (current status: {current_status})")
                    await db.incoming_messages.update_one(
                        {"id": main_message.id, "channel_id": main_message.chat_id},
                        {"$set": {"processing_status": "pending"}}
                    )
                else:
                    # Skip if already successfully processed (unless it's an error)
                    if current_status in ["parsed", "filtered", "forwarded", "spam_filtered", "not_real_estate", "media_only"]:
                        logger.debug(f"Message {main_message.id} already processed with status {current_status}, skipping")
                        stats['skipped'] += 1
                        continue
                    elif current_status == "error":
                        logger.info(f"Message {main_message.id} had error status, reprocessing")
                        await db.incoming_messages.update_one(
                            {"id": main_message.id, "channel_id": main_message.chat_id},
                            {"$set": {"processing_status": "pending"}}
                        )
                    else:
                        logger.info(f"Message {main_message.id} has status {current_status}, reprocessing")
                        await db.incoming_messages.update_one(
                            {"id": main_message.id, "channel_id": main_message.chat_id},
                            {"$set": {"processing_status": "pending"}}
                        )
            else:
                logger.info(f"Message {main_message.id} not found in database, processing for first time")
            
            # Process the main message
            await self._process_message(main_message, force)
            
            # Only count messages with text (not media-only)
            if not self._is_media_only_message(main_message):
                stats['total_processed'] += 1
            
            # Update statistics based on final status
            post = await db.incoming_messages.find_one({
                "id": main_message.id, 
                "channel_id": main_message.chat_id
            })
            
            if post:
                if post.get("processing_status") == "spam_filtered":
                    stats['spam_filtered'] += 1
                elif post.get("processing_status") == "media_only":
                    # Media-only messages are not counted in main stats
                    pass
                elif post.get("processing_status") == "not_real_estate":
                    stats['not_real_estate'] += 1
                elif post.get("processing_status") in ["parsed", "filtered", "forwarded"]:
                    stats['real_estate_ads'] += 1
                    
                    # Check if it matched filters
                    real_estate_ad = await db.real_estate_ads.find_one({
                        "original_post_id": main_message.id,
                        "original_channel_id": main_message.chat_id
                    })
                    
                    if real_estate_ad and real_estate_ad.get("matched_filters"):
                        stats['matched_filters'] += 1
                    
                    if post.get("processing_status") == "forwarded":
                        stats['forwarded'] += 1
                elif post.get("processing_status") == "error":
                    stats['errors'] += 1
        
        logger.info(f"Reprocessing completed: {stats}")
        return stats
    
    def _get_property_type_name(self, property_type) -> str:
        """Convert property type enum to Russian name"""
        type_names = {
            "apartment": "Квартира",
            "house": "Дом", 
            "room": "Комната",
            "hotel_room": "Гостиничный номер"
        }
        return type_names.get(property_type, property_type)
    
    async def _get_filter_name(self, filter_id: str) -> str:
        """Get filter name by MongoDB _id"""
        try:
            from bson import ObjectId
            logger.info(f"Getting filter name for ID: {filter_id}")
            object_id = ObjectId(filter_id)
            db = mongodb.get_database()
            
            # Try simple_filters collection first (where filters are actually stored)
            filter_doc = await db.simple_filters.find_one({"_id": object_id})
            logger.info(f"Filter document found in simple_filters: {filter_doc}")
            
            if filter_doc:
                name = filter_doc["name"]
                logger.info(f"Filter name: {name}")
                return name
            
            # Fallback to filters collection
            filter_doc = await db.filters.find_one({"_id": object_id})
            logger.info(f"Filter document found in filters: {filter_doc}")
            
            if filter_doc:
                name = filter_doc["name"]
                logger.info(f"Filter name: {name}")
                return name
            else:
                logger.warning(f"Filter not found for ID: {filter_id}")
                return f"Фильтр {filter_id[:8]}..."
                
        except Exception as e:
            logger.error(f"Error getting filter name: {e}")
            return f"Фильтр {filter_id[:8]}..."
    
    def _get_message_link(self, channel_id, message_id, topic_id=None) -> str:
        """Generate link to original message in channel"""
        # Convert to int if it's a Long object
        if hasattr(channel_id, 'value'):
            channel_id = channel_id.value
        if hasattr(message_id, 'value'):
            message_id = message_id.value
        if hasattr(topic_id, 'value'):
            topic_id = topic_id.value
            
        # For channels with topics, use @username/topic_id/message_id format
        if topic_id:
            # This is a topic-based channel, use the topic format
            # Get channel username from settings
            channel_username = settings.TELEGRAM_CHANNEL_USERNAME
            return f"https://t.me/{channel_username}/{topic_id}/{message_id}"
        else:
            # Regular channel, use c/channel_id/message_id format
            if channel_id < 0:
                channel_id = abs(channel_id) - 1000000000000
            return f"https://t.me/c/{channel_id}/{message_id}"
    
    async def _format_real_estate_message(self, real_estate_ad, original_message, filter_id: str = None):
        """Format real estate ad for forwarding"""
        message = f"🏠 **Найдено подходящее объявление!**\n\n"
        
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
            contacts_str = ", ".join(real_estate_ad.contacts) if isinstance(real_estate_ad.contacts, list) else str(real_estate_ad.contacts)
            message += f"**Контакты:** {contacts_str}\n"
        
        # Add filter matching information
        if real_estate_ad.matched_filters:
            message += f"\n**✅ Соответствует фильтрам:** {len(real_estate_ad.matched_filters)}\n"
            if filter_id:
                filter_name = await self._get_filter_name(filter_id)
                message += f"**🎯 Активный фильтр:** {filter_name}\n"
        
        message += f"\n**Уверенность:** {real_estate_ad.parsing_confidence:.2f}\n"
        
        # Add original message link
        message_link = self._get_message_link(real_estate_ad.original_channel_id, real_estate_ad.original_post_id, real_estate_ad.original_topic_id)
        message += f"\n**Оригинальный текст:**\n{real_estate_ad.original_message[:300]}...\n\n"
        message += f"🔗 [Читать полностью]({message_link})"
        
        return message
    
    async def refilter_ads(self, count: int) -> dict:
        """Refilter existing ads without reprocessing"""
        try:
            logger.info(f"Starting refilter for {count} ads")
            
            # Get database connection
            db = mongodb.get_database()
            
            # Get recent real estate ads from database
            real_estate_ads_cursor = db.real_estate_ads.find().sort("_id", -1).limit(count)
            ads_list = []
            async for ad_doc in real_estate_ads_cursor:
                ads_list.append(ad_doc)
            
            logger.info(f"Found {len(ads_list)} ads to refilter")
            
            total_checked = 0
            matched_filters = 0
            forwarded = 0
            errors = 0
            
            # Get user filters
            user_filters_cursor = db.simple_filters.find({"is_active": True})
            user_filters = []
            async for filter_doc in user_filters_cursor:
                user_filters.append(filter_doc)
            logger.info(f"Found {len(user_filters)} active filters")
            
            if not user_filters:
                logger.warning("No active filters found")
                return {
                    "total_checked": len(ads_list),
                    "matched_filters": 0,
                    "forwarded": 0,
                    "errors": 0,
                    "message": "No active filters found"
                }
            
            # Process each ad
            for ad_doc in ads_list:
                try:
                    total_checked += 1
                    
                    # Convert to RealEstateAd object
                    from app.models.telegram import RealEstateAd
                    ad = RealEstateAd(**ad_doc)
                    
                    # Check against all filters
                    matched_any_filter = False
                    for filter_doc in user_filters:
                        from app.models.simple_filter import SimpleFilter
                        filter_obj = SimpleFilter(**filter_doc)
                        
                        if filter_obj.matches(ad):
                            matched_any_filter = True
                            matched_filters += 1
                            logger.info(f"Ad {ad.original_post_id} matched filter {filter_obj.name}")
                            
                            # Forward the ad
                            try:
                                # Create a mock message object for forwarding
                                from unittest.mock import MagicMock
                                mock_message = MagicMock()
                                mock_message.chat_id = ad.original_channel_id
                                mock_message.id = ad.original_post_id
                                
                                await self._forward_post(mock_message, ad, filter_obj.id)
                                forwarded += 1
                                logger.info(f"Ad {ad.original_post_id} forwarded successfully")
                            except Exception as e:
                                logger.error(f"Error forwarding ad {ad.original_post_id}: {e}")
                                errors += 1
                            
                            # Only forward to first matching filter
                            break
                    
                    if not matched_any_filter:
                        logger.debug(f"Ad {ad.original_post_id} did not match any filters")
                        
                except Exception as e:
                    logger.error(f"Error processing ad {ad_doc.get('_id')}: {e}")
                    errors += 1
            
            result = {
                "total_checked": total_checked,
                "matched_filters": matched_filters,
                "forwarded": forwarded,
                "errors": errors
            }
            
            logger.info(f"Refilter completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in refilter_ads: {e}")
            raise
