import asyncio
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from bson import ObjectId
from telethon.tl.types import Message

from app.core.config import settings
from app.db.mongodb import mongodb
from app.exceptions import LLMQuotaExceededError
from app.models.incoming_message import IncomingMessage
from app.models.price_filter import PriceFilter
from app.models.simple_filter import SimpleFilter
from app.models.status_enums import IncomingMessageStatus, RealEstateAdStatus
from app.models.telegram import RealEstateAd
from app.services.admin_notification_service import admin_notification_service
from app.services.filter_service import FilterService
from app.services.llm_service import LLMService
from app.services.llm_quota_service import llm_quota_service
from app.services.user_service import user_service

if TYPE_CHECKING:
    from app.services.telegram.client_manager import TelegramClientManager
    from app.services.telegram.message_forwarder import MessageForwarder
    from app.services.telegram.message_validator import MessageValidator

logger = logging.getLogger(__name__)


class MessageProcessor:
    """LLM parsing, duplicate detection, filter matching, reprocessing."""

    def __init__(
        self,
        client_manager: "TelegramClientManager",
        validator: "MessageValidator",
        forwarder: "MessageForwarder",
    ) -> None:
        self.client_manager = client_manager
        self.validator = validator
        self.forwarder = forwarder
        self.llm_service = LLMService()
        self.filter_service = FilterService()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _generate_message_hash(self, message_text: str) -> str:
        normalized_text = ' '.join(message_text.strip().split()).lower()
        return hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()

    def _group_messages_by_grouped_id(self, messages: List[Any]) -> Dict[Any, List[Any]]:
        groups: Dict[Any, List[Any]] = {}
        for message in messages:
            grouped_id = getattr(message, "grouped_id", None)
            if grouped_id:
                if grouped_id not in groups:
                    groups[grouped_id] = []
                groups[grouped_id].append(message)
            else:
                groups[f"single_{message.id}"] = [message]

        for _, msgs in groups.items():
            msgs.sort(key=lambda x: x.date)
        return groups

    # ------------------------------------------------------------------
    # Main processing pipeline
    # ------------------------------------------------------------------

    async def _process_message(self, message: Message, force: bool = False, user_id: Optional[int] = None) -> None:
        real_estate_ad = None
        try:
            if not await self.validator._is_from_monitored_subchannel(message):
                return

            if self.validator._is_media_only_message(message):
                return
            if message.text:
                logger.info("Message text: %s", message.text[:200] + "..." if len(message.text) > 200 else message.text)

            message_text = message.text or ""
            message_hash = self._generate_message_hash(message_text)

            channel_title = "Unknown"
            try:
                if message.chat and hasattr(message.chat, "title"):
                    channel_title = message.chat.title
            except Exception as e:
                logger.warning("Could not get channel title for message %s: %s", message.id, e)

            db = mongodb.get_database()
            existing_ad = await db.real_estate_ads.find_one({"original_post_id": message.id})
            if existing_ad and not force:
                logger.info("Found existing RealEstateAd for message %s, skipping LLM parsing", message.id)
                real_estate_ad = RealEstateAd(**existing_ad)
                logger.info("Checking filters for duplicate message %s (original ad: %s)", message.id, existing_ad["_id"])
                await self._check_filters_for_all_users(real_estate_ad, message)

                existing_post = await db.incoming_messages.find_one({"id": message.id, "channel_id": message.chat_id})
                if existing_post:
                    await db.incoming_messages.update_one(
                        {"id": message.id, "channel_id": message.chat_id},
                        {"$set": {
                            "processing_status": IncomingMessageStatus.DUPLICATE,
                            "real_estate_ad_id": str(existing_ad["_id"]),
                            "updated_at": datetime.now(timezone.utc)
                        }}
                    )
                    logger.info("Updated existing IncomingMessage %s to DUPLICATE status", message.id)
                    await self.forwarder._mark_message_as_read(message)
                else:
                    duplicate_data = {
                        "id": message.id,
                        "channel_id": message.chat_id,
                        "channel_title": channel_title,
                        "message_text": message_text,
                        "message_hash": message_hash,
                        "date": message.date,
                        "views": getattr(message, "views", None),
                        "forwards": getattr(message, "forwards", None),
                        "processing_status": IncomingMessageStatus.DUPLICATE,
                        "is_real_estate": existing_ad.get("is_real_estate"),
                        "real_estate_ad_id": str(existing_ad["_id"]),
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                    await db.incoming_messages.insert_one(duplicate_data)
                    logger.info("Saved duplicate message %s with DUPLICATE status", message.id)
                    await self.forwarder._mark_message_as_read(message)
                return

            existing_post = await db.incoming_messages.find_one({"id": message.id, "channel_id": message.chat_id})

            if existing_post:
                existing_status = existing_post.get("processing_status")
                if existing_status == IncomingMessageStatus.DELETED:
                    logger.debug("Skipping message %s - status is DELETED", message.id)
                    return

                if existing_status == IncomingMessageStatus.ERROR and not force:
                    parsing_errors = existing_post.get("parsing_errors", [])
                    is_quota_error = any("quota" in str(err).lower() or "insufficient" in str(err).lower()
                                         for err in parsing_errors)
                    if is_quota_error and llm_quota_service.is_quota_exceeded():
                        logger.info("Skipping message %s with quota error status (quota still exceeded)", message.id)
                        return

                if not force and existing_status not in [IncomingMessageStatus.ERROR, IncomingMessageStatus.PROCESSING]:
                    return

                logger.info("Reprocessing message %s (previous status: %s)", message.id, existing_post.get("processing_status"))

            duplicate_by_hash = await db.incoming_messages.find_one({
                "message_hash": message_hash,
                "id": {"$ne": message.id}
            })

            if duplicate_by_hash and not force:
                logger.info("Found duplicate message by hash: %s (original: %s)", message.id, duplicate_by_hash["id"])
                ch_title = "Unknown"
                try:
                    if message.chat and hasattr(message.chat, "title"):
                        ch_title = message.chat.title
                except Exception:
                    pass

                duplicate_data = {
                    "id": message.id,
                    "channel_id": message.chat_id,
                    "channel_title": ch_title,
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
                await self.forwarder._mark_message_as_read(message)

                if duplicate_by_hash.get("real_estate_ad_id"):
                    real_estate_ad_doc = await db.real_estate_ads.find_one({"_id": ObjectId(duplicate_by_hash["real_estate_ad_id"])})
                    if real_estate_ad_doc:
                        real_estate_ad = RealEstateAd(**real_estate_ad_doc)
                        logger.info("Checking filters for duplicate message %s (original ad: %s)", message.id, duplicate_by_hash["real_estate_ad_id"])
                        await self._check_filters_for_all_users(real_estate_ad, message)

                logger.info("Duplicate message %s processed without LLM parsing", message.id)
                return

            channel_title = "Unknown"
            try:
                if message.chat and hasattr(message.chat, "title"):
                    channel_title = message.chat.title
            except Exception:
                pass

            post_data = {
                "id": message.id,
                "channel_id": message.chat_id,
                "channel_title": channel_title,
                "message": message.text or "",
                "message_hash": message_hash,
                "date": message.date,
                "views": getattr(message, "views", None),
                "forwards": getattr(message, "forwards", None),
                "replies": None,
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

            if existing_post:
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id}, {"$set": post_data}
                )
                incoming_message_id = str(existing_post["_id"])
                await self.forwarder._mark_message_as_read(message)
            else:
                result = await db.incoming_messages.insert_one(post_data)
                incoming_message_id = str(result.inserted_id)
                await self.forwarder._mark_message_as_read(message)

            message_text = message.text or ""
            logger.info("Message %s: text='%s', has_text=%s", message.id, message_text, bool(message.text))

            if self.validator._is_technical_bot_message(message_text):
                logger.info("Message %s is a technical bot message, skipping", message.id)
                return

            if message_text:
                if llm_quota_service.is_quota_exceeded():
                    logger.warning("Skipping LLM processing for message %s - quota exceeded", message.id)
                    await db.incoming_messages.update_one(
                        {"id": message.id, "channel_id": message.chat_id},
                        {"$set": {
                            "processing_status": IncomingMessageStatus.ERROR,
                            "parsing_errors": ["LLM quota exceeded - processing skipped"],
                            "processed_at": message.date,
                            "updated_at": message.date,
                        }},
                    )
                    return

                logger.info("Processing message %s with LLM", message.id)
                parse_start_time = time.time()

                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {"$set": {"processing_status": IncomingMessageStatus.PROCESSING, "updated_at": message.date}},
                )

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
                incoming_message_obj._id = incoming_message_id

                real_estate_ad = await self.llm_service.parse_with_llm(
                    incoming_message_obj.message,
                    incoming_message_obj.id,
                    incoming_message_obj.channel_id,
                    incoming_message_id,
                    incoming_message_obj.topic_id,
                )

                parse_duration = time.time() - parse_start_time
                logger.info("LLM parsing completed for message %s in %.2f seconds", message.id, parse_duration)

                if real_estate_ad is None:
                    existing_post = await db.incoming_messages.find_one({"id": message.id, "channel_id": message.chat_id})
                    existing_status = existing_post.get("processing_status") if existing_post else None
                    parsing_errors = existing_post.get("parsing_errors", []) if existing_post else []

                    if parsing_errors:
                        logger.warning("LLM parsing returned None for message %s, but status is ERROR with errors - keeping ERROR status", message.id)
                        if existing_status != IncomingMessageStatus.ERROR:
                            await db.incoming_messages.update_one(
                                {"id": message.id, "channel_id": message.chat_id},
                                {"$set": {
                                    "processing_status": IncomingMessageStatus.ERROR,
                                    "parsing_errors": parsing_errors,
                                    "updated_at": message.date,
                                }},
                            )
                    else:
                        logger.info("LLM parsing returned None for message %s without errors - setting to NOT_REAL_ESTATE", message.id)
                        await db.incoming_messages.update_one(
                            {"id": message.id, "channel_id": message.chat_id},
                            {"$set": {
                                "processing_status": IncomingMessageStatus.NOT_REAL_ESTATE,
                                "is_real_estate": False,
                                "parsing_errors": [],
                                "updated_at": message.date,
                            }},
                        )
                    return

                if real_estate_ad:
                    if real_estate_ad.is_real_estate:
                        ad_data = real_estate_ad.model_dump(exclude={"id"}, by_alias=False)
                        result = await db.real_estate_ads.replace_one(
                            {"original_post_id": message.id}, ad_data, upsert=True
                        )
                        if result.upserted_id:
                            real_estate_ad.id = str(result.upserted_id)
                            logger.info("Created new RealEstateAd with id: %s", real_estate_ad.id)
                        else:
                            existing = await db.real_estate_ads.find_one({"original_post_id": message.id})
                            if existing:
                                real_estate_ad.id = str(existing["_id"])
                                logger.info("Updated existing RealEstateAd with id: %s", real_estate_ad.id)

                        await db.incoming_messages.update_one(
                            {"id": message.id, "channel_id": message.chat_id},
                            {"$set": {
                                "processing_status": IncomingMessageStatus.PARSED,
                                "is_real_estate": True,
                                "real_estate_confidence": real_estate_ad.parsing_confidence,
                                "real_estate_ad_id": real_estate_ad.id,
                                "updated_at": message.date,
                            }},
                        )
                        await self._check_filters_for_all_users(real_estate_ad, message)
                    else:
                        await db.incoming_messages.update_one(
                            {"id": message.id, "channel_id": message.chat_id},
                            {"$set": {
                                "processing_status": IncomingMessageStatus.NOT_REAL_ESTATE,
                                "is_real_estate": False,
                                "updated_at": message.date,
                            }},
                        )
            else:
                logger.info("Message %s has no text, skipping LLM processing", message.id)
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {"$set": {
                        "processing_status": "no_text",
                        "is_real_estate": False,
                        "processed_at": message.date,
                        "updated_at": message.date,
                    }},
                )

            if real_estate_ad:
                pass
            else:
                logger.info("Message %s not identified as real estate ad by LLM", message.id)
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {"$set": {
                        "processing_status": IncomingMessageStatus.NOT_REAL_ESTATE,
                        "is_real_estate": False,
                        "processed_at": message.date,
                        "updated_at": message.date,
                    }},
                )

        except LLMQuotaExceededError as e:
            db = mongodb.get_database()
            if e.is_quota:
                logger.error("LLM quota exceeded (no balance) while processing message %s: %s", message.id, e)
                try:
                    await db.incoming_messages.update_one(
                        {"id": message.id, "channel_id": message.chat_id},
                        {"$set": {
                            "processing_status": IncomingMessageStatus.ERROR,
                            "parsing_errors": [f"LLM quota exceeded ({e.provider}): {e.message}"],
                            "processed_at": message.date,
                            "updated_at": message.date,
                        }},
                    )
                except Exception as update_error:
                    logger.error("Error updating message status to error: %s", update_error)

            elif e.is_concurrency or e.is_rate_limit:
                error_type = "concurrency" if e.is_concurrency else "rate limit"
                logger.warning("LLM %s exceeded while processing message %s: %s. Will retry.", error_type, message.id, e)
                try:
                    existing_msg = await db.incoming_messages.find_one({"id": message.id, "channel_id": message.chat_id})
                    retry_count = existing_msg.get("retry_count", 0) + 1 if existing_msg else 1
                    retry_delay = min(30 * (2 ** (retry_count - 1)), 480)
                    retry_after = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)

                    await db.incoming_messages.update_one(
                        {"id": message.id, "channel_id": message.chat_id},
                        {"$set": {
                            "processing_status": IncomingMessageStatus.RETRY,
                            "parsing_errors": [f"LLM {error_type} exceeded ({e.provider}): {e.message}"],
                            "retry_count": retry_count,
                            "retry_after": retry_after,
                            "updated_at": message.date,
                        }},
                    )
                    logger.info("Message %s set to RETRY (attempt %d, delay %ds, retry after %s)",
                                message.id, retry_count, retry_delay, retry_after)

                    if e.is_concurrency:
                        try:
                            asyncio.create_task(
                                admin_notification_service.notify_rate_limit_exceeded(str(e), retry_count, retry_delay)
                            )
                        except Exception as notify_error:
                            logger.error("Error creating notification task: %s", notify_error)

                except Exception as update_error:
                    logger.error("Error updating message status to retry: %s", update_error)
            else:
                logger.error("LLM error while processing message %s: %s", message.id, e)
                try:
                    await db.incoming_messages.update_one(
                        {"id": message.id, "channel_id": message.chat_id},
                        {"$set": {
                            "processing_status": IncomingMessageStatus.ERROR,
                            "parsing_errors": [f"LLM error ({e.provider}): {e.message}"],
                            "processed_at": message.date,
                            "updated_at": message.date,
                        }},
                    )
                except Exception as update_error:
                    logger.error("Error updating message status to error: %s", update_error)
        except Exception as e:
            logger.error("Error processing message: %s", e)
            try:
                db = mongodb.get_database()
                await db.incoming_messages.update_one(
                    {"id": message.id, "channel_id": message.chat_id},
                    {"$set": {
                        "processing_status": IncomingMessageStatus.ERROR,
                        "parsing_errors": [str(e)],
                        "processed_at": message.date,
                        "updated_at": message.date,
                    }},
                )
            except Exception as update_error:
                logger.error("Error updating post status to error: %s", update_error)

    # ------------------------------------------------------------------
    # Filter checking (batch optimized)
    # ------------------------------------------------------------------

    async def _check_filters_for_all_users(self, real_estate_ad: RealEstateAd, message: Message) -> None:
        """
        Check filters for ALL users and forward to matching users.

        Uses batch queries to avoid N+1 problem:
        ~6 queries total instead of ~100+ for 30 filters.
        """
        try:
            db = mongodb.get_database()

            all_filters = await db.simple_filters.find({"is_active": True}).to_list(length=None)
            if not all_filters:
                logger.info("No active filters found for ad %s", message.id)
                return

            logger.info("Checking %d filters for ad %s (message_id=%s)", len(all_filters), real_estate_ad.original_post_id, message.id)

            from app.utils.channel_id_utils import channel_id_to_string
            normalized_str = channel_id_to_string(message.chat_id)

            monitored_channel = await db.monitored_channels.find_one({
                "channel_id": normalized_str, "is_active": True
            })
            if not monitored_channel:
                monitored_channel = await db.monitored_channels.find_one({
                    "channel_id": str(message.chat_id), "is_active": True
                })

            selected_user_ids = set()
            if monitored_channel:
                monitored_channel_id = str(monitored_channel["_id"])
                selections_cursor = db.user_channel_selections.find({
                    "channel_id": monitored_channel_id, "is_selected": True
                })
                async for sel in selections_cursor:
                    selected_user_ids.add(sel["user_id"])
            else:
                logger.warning("Channel %s not found in monitored_channels, no users will match", message.chat_id)

            filter_ids = [str(f["_id"]) for f in all_filters]
            all_price_filters_docs = await db.price_filters.find({
                "filter_id": {"$in": filter_ids}, "is_active": True
            }).to_list(length=None)

            price_filters_by_id: Dict[str, list] = {}
            for doc in all_price_filters_docs:
                fid = doc["filter_id"]
                doc_copy = dict(doc)
                doc_copy["id"] = str(doc_copy.pop("_id"))
                if "is_active" not in doc_copy:
                    doc_copy["is_active"] = True
                try:
                    pf = PriceFilter(**doc_copy)
                    price_filters_by_id.setdefault(fid, []).append(pf)
                except Exception as e:
                    logger.error("Validation error for price filter %s: %s", doc.get("_id"), e)

            ad_id = real_estate_ad.id if real_estate_ad.id else None
            if not ad_id:
                existing_ad = await db.real_estate_ads.find_one({"original_post_id": real_estate_ad.original_post_id})
                if existing_ad:
                    ad_id = str(existing_ad["_id"])

            already_sent_users = set()
            if ad_id:
                sent_cursor = db.outgoing_posts.find({
                    "real_estate_ad_id": ad_id, "incoming_message_id": message.id
                })
                async for sent_doc in sent_cursor:
                    already_sent_users.add(sent_doc.get("sent_to"))

            if not ad_id:
                logger.warning("Could not determine ad_id for ad %s, skipping duplicate check", real_estate_ad.original_post_id)

            for filter_doc in all_filters:
                try:
                    filter_obj = SimpleFilter(**filter_doc)
                    user_id = filter_obj.user_id
                    filter_id = str(filter_doc["_id"])

                    if user_id not in selected_user_ids:
                        logger.debug("User %s has not selected channel %s, skipping filter '%s'", user_id, message.chat_id, filter_obj.name)
                        continue

                    price_filters = price_filters_by_id.get(filter_id, [])
                    if filter_obj.matches_with_price_filters(real_estate_ad, price_filters):
                        logger.info("Ad %s matches filter '%s' for user %s", message.id, filter_obj.name, user_id)

                        if ad_id and str(user_id) in already_sent_users:
                            logger.info("Ad %s (message %s) already sent to user %s, skipping", ad_id, message.id, user_id)
                            continue

                        await self.forwarder._forward_post(message, real_estate_ad, filter_id, filter_obj.name, user_id)
                    else:
                        logger.debug("Ad %s does not match filter '%s' for user %s", message.id, filter_obj.name, user_id)

                except Exception as e:
                    logger.error("Error checking filter %s for ad %s: %s", filter_doc.get("_id"), message.id, e)
                    continue

            await db.incoming_messages.update_one(
                {
                    "id": message.id,
                    "channel_id": message.chat_id,
                    "processing_status": {"$ne": IncomingMessageStatus.DUPLICATE}
                },
                {"$set": {"processing_status": IncomingMessageStatus.PARSED, "updated_at": message.date}},
            )

        except Exception as e:
            logger.error("Error checking filters for all users: %s", e)

    # ------------------------------------------------------------------
    # Reprocess stuck messages
    # ------------------------------------------------------------------

    async def _reprocess_stuck_messages(self) -> None:
        try:
            logger.info("Checking for stuck messages (PROCESSING, ERROR, or RETRY status)...")

            if llm_quota_service.is_quota_exceeded():
                logger.info("LLM quota exceeded - skipping reprocessing of stuck messages")
                return

            db = mongodb.get_database()
            current_time = datetime.now(timezone.utc)

            stuck_messages = []
            async for message_doc in db.incoming_messages.find({
                "$and": [
                    {"processing_status": {"$in": [
                        IncomingMessageStatus.PROCESSING,
                        IncomingMessageStatus.ERROR,
                        IncomingMessageStatus.RETRY
                    ]}},
                    {"processing_status": {"$ne": IncomingMessageStatus.DELETED}}
                ]
            }):
                if message_doc["processing_status"] == IncomingMessageStatus.ERROR:
                    parsing_errors = message_doc.get("parsing_errors", [])
                    error_str = " ".join(str(e) for e in parsing_errors).lower()

                    is_deletion_error = any(keyword in error_str for keyword in [
                        "not found", "deleted", "message not found", "channel not found",
                        "chat not found", "access denied", "forbidden", "not accessible"
                    ])

                    if is_deletion_error:
                        logger.info("Message %s has deletion-related error, marking as DELETED: %s",
                                    message_doc["id"], parsing_errors)
                        try:
                            await db.incoming_messages.update_one(
                                {"id": message_doc["id"], "channel_id": message_doc["channel_id"]},
                                {"$set": {
                                    "processing_status": IncomingMessageStatus.DELETED,
                                    "parsing_errors": parsing_errors,
                                    "updated_at": datetime.now(timezone.utc)
                                }}
                            )
                            continue
                        except Exception as e:
                            logger.error("Error marking message %s as DELETED: %s", message_doc["id"], e)

                    is_quota_error = any(
                        "quota" in str(error).lower() or "insufficient" in str(error).lower()
                        for error in parsing_errors
                    )
                    if is_quota_error and llm_quota_service.is_quota_exceeded():
                        logger.info("Skipping message %s with quota error status (quota still exceeded)", message_doc["id"])
                        continue

                if message_doc["processing_status"] == IncomingMessageStatus.RETRY:
                    retry_after = message_doc.get("retry_after")
                    if retry_after:
                        if retry_after.tzinfo is None:
                            retry_after = retry_after.replace(tzinfo=timezone.utc)
                        if retry_after > current_time:
                            logger.debug("Skipping message %s - retry scheduled for %s", message_doc["id"], retry_after)
                            continue

                stuck_messages.append({
                    "id": message_doc["id"],
                    "channel_id": message_doc["channel_id"],
                    "status": message_doc["processing_status"],
                    "retry_count": message_doc.get("retry_count", 0)
                })

            if not stuck_messages:
                logger.info("No stuck messages found")
                return

            logger.info("Found %d stuck messages to reprocess", len(stuck_messages))

            processed_count = 0
            error_count = 0
            skipped_count = 0

            client = self.client_manager.client

            for msg_info in stuck_messages:
                try:
                    message_id = msg_info["id"]
                    channel_id = msg_info["channel_id"]
                    status = msg_info["status"]

                    if llm_quota_service.is_quota_exceeded():
                        logger.info("LLM quota exceeded - skipping reprocessing of message %s", message_id)
                        skipped_count += 1
                        continue

                    logger.info("Reprocessing stuck message %s from channel %s (status: %s)",
                                message_id, channel_id, status)

                    if not client or not client.is_connected():
                        logger.warning("Telegram client not connected, skipping message %s", message_id)
                        continue

                    try:
                        try:
                            channel_entity = await client.get_entity(channel_id)
                        except Exception as e:
                            error_str = str(e).lower()
                            if "not found" in error_str or "chat not found" in error_str or "channel not found" in error_str:
                                logger.info("Channel %s not found or access denied, marking message %s as DELETED", channel_id, message_id)
                                await db.incoming_messages.update_one(
                                    {"id": message_id, "channel_id": channel_id},
                                    {"$set": {
                                        "processing_status": IncomingMessageStatus.DELETED,
                                        "parsing_errors": [f"Channel not found or access denied: {str(e)}"],
                                        "updated_at": datetime.now(timezone.utc)
                                    }}
                                )
                                skipped_count += 1
                            else:
                                logger.warning("Could not get channel entity for %s: %s, skipping message %s", channel_id, e, message_id)
                                error_count += 1
                            continue

                        messages = await client.get_messages(channel_entity, ids=message_id)
                        if isinstance(messages, list):
                            message = messages[0] if messages else None
                        else:
                            message = messages

                        if not message:
                            logger.info("Message %s not found in channel %s (likely deleted), marking as DELETED", message_id, channel_id)
                            existing = await db.incoming_messages.find_one({"id": message_id, "channel_id": channel_id})
                            if existing and existing.get("processing_status") != IncomingMessageStatus.DELETED:
                                await db.incoming_messages.update_one(
                                    {"id": message_id, "channel_id": channel_id},
                                    {"$set": {
                                        "processing_status": IncomingMessageStatus.DELETED,
                                        "parsing_errors": ["Message deleted from channel"],
                                        "updated_at": datetime.now(timezone.utc)
                                    }}
                                )
                            skipped_count += 1
                            continue

                        if llm_quota_service.is_quota_exceeded():
                            logger.info("Skipping reprocessing of message %s - LLM quota exceeded", message_id)
                            skipped_count += 1
                            continue

                        await self._process_message(message, force=False)
                        await asyncio.sleep(0.5)

                        updated_post = await db.incoming_messages.find_one({"id": message_id, "channel_id": channel_id})
                        if updated_post and updated_post.get("processing_status") == IncomingMessageStatus.ERROR:
                            parsing_errors = updated_post.get("parsing_errors", [])
                            error_str = " ".join(str(e) for e in parsing_errors).lower()

                            is_deletion_error = False
                            deletion_reason = None

                            if not parsing_errors:
                                logger.warning("Message %s has ERROR status but no parsing_errors recorded", message_id)
                                try:
                                    check_messages = await client.get_messages(channel_entity, ids=message_id)
                                    message_exists = bool(check_messages[0]) if isinstance(check_messages, list) and check_messages else bool(check_messages)

                                    if not message_exists:
                                        is_deletion_error = True
                                        deletion_reason = "Message not found in channel (no errors recorded, message deleted)"
                                    else:
                                        logger.info("Message %s exists but has ERROR status without errors - setting to NOT_REAL_ESTATE", message_id)
                                        await db.incoming_messages.update_one(
                                            {"id": message_id, "channel_id": channel_id},
                                            {"$set": {
                                                "processing_status": IncomingMessageStatus.NOT_REAL_ESTATE,
                                                "parsing_errors": [],
                                                "is_real_estate": False,
                                                "updated_at": datetime.now(timezone.utc)
                                            }}
                                        )
                                        processed_count += 1
                                        continue
                                except Exception as check_error:
                                    check_error_str = str(check_error).lower()
                                    if any(keyword in check_error_str for keyword in ["not found", "deleted", "message not found"]):
                                        is_deletion_error = True
                                        deletion_reason = f"Error checking message existence: {str(check_error)}"
                                    else:
                                        logger.warning("Could not check if message %s exists: %s - leaving as ERROR", message_id, check_error)

                            if not is_deletion_error and any(keyword in error_str for keyword in [
                                "not found", "deleted", "message not found", "channel not found",
                                "chat not found", "access denied", "forbidden", "not accessible"
                            ]):
                                is_deletion_error = True
                                deletion_reason = f"Error indicates message was deleted: {parsing_errors}"

                            if is_deletion_error:
                                logger.info("Message %s has deletion-related error, marking as DELETED: %s", message_id, deletion_reason)
                                await db.incoming_messages.update_one(
                                    {"id": message_id, "channel_id": channel_id},
                                    {"$set": {
                                        "processing_status": IncomingMessageStatus.DELETED,
                                        "parsing_errors": parsing_errors if parsing_errors else [deletion_reason],
                                        "updated_at": datetime.now(timezone.utc)
                                    }}
                                )
                                skipped_count += 1
                            elif not parsing_errors:
                                logger.info("Message %s has ERROR status without errors - setting to NOT_REAL_ESTATE", message_id)
                                await db.incoming_messages.update_one(
                                    {"id": message_id, "channel_id": channel_id},
                                    {"$set": {
                                        "processing_status": IncomingMessageStatus.NOT_REAL_ESTATE,
                                        "parsing_errors": [],
                                        "is_real_estate": False,
                                        "updated_at": datetime.now(timezone.utc)
                                    }}
                                )
                                processed_count += 1
                            else:
                                is_concurrency_error = '1302' in error_str or 'concurrency' in error_str or 'high concurrency' in error_str
                                is_rate_limit_error = 'rate limit' in error_str or 'too many requests' in error_str

                                if is_concurrency_error or is_rate_limit_error:
                                    error_type = "concurrency" if is_concurrency_error else "rate limit"
                                    logger.info("Message %s has %s error - converting to RETRY status", message_id, error_type)
                                    retry_count = updated_post.get("retry_count", 0) + 1
                                    retry_delay = min(30 * (2 ** (retry_count - 1)), 480)
                                    retry_after = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)

                                    await db.incoming_messages.update_one(
                                        {"id": message_id, "channel_id": channel_id},
                                        {"$set": {
                                            "processing_status": IncomingMessageStatus.RETRY,
                                            "retry_count": retry_count,
                                            "retry_after": retry_after,
                                            "updated_at": datetime.now(timezone.utc)
                                        }}
                                    )
                                    logger.info("Message %s set to RETRY (attempt %d, delay %ds, retry after %s)",
                                                message_id, retry_count, retry_delay, retry_after)
                                    processed_count += 1
                                else:
                                    error_count += 1
                                    current_provider = self.llm_service.provider
                                    current_model = self.llm_service.model
                                    logger.warning("Message %s still has ERROR status after reprocessing (current LLM: %s/%s). Errors: %s",
                                                   message_id, current_provider, current_model, parsing_errors)
                        else:
                            processed_count += 1
                            logger.info("Successfully reprocessed stuck message %s", message_id)

                    except Exception as e:
                        error_str = str(e).lower()
                        if "not found" in error_str or "deleted" in error_str or "message not found" in error_str:
                            logger.info("Message %s not found in channel (likely deleted), marking as DELETED", message_id)
                            await db.incoming_messages.update_one(
                                {"id": message_id, "channel_id": channel_id},
                                {"$set": {
                                    "processing_status": IncomingMessageStatus.DELETED,
                                    "parsing_errors": [f"Message not found in channel: {str(e)}"],
                                    "updated_at": datetime.now(timezone.utc)
                                }}
                            )
                            skipped_count += 1
                        else:
                            logger.error("Error getting/reprocessing message %s: %s", message_id, e)
                            error_count += 1
                            try:
                                await db.incoming_messages.update_one(
                                    {"id": message_id, "channel_id": channel_id},
                                    {"$set": {
                                        "processing_status": IncomingMessageStatus.ERROR,
                                        "parsing_errors": [f"Reprocessing error: {str(e)}"],
                                        "updated_at": datetime.now(timezone.utc)
                                    }}
                                )
                            except Exception as update_error:
                                logger.error("Error updating message %s status: %s", message_id, update_error)

                except Exception as e:
                    logger.error("Error processing stuck message %s: %s", msg_info.get("id"), e)
                    error_count += 1

            logger.info("Stuck messages reprocessing completed: processed %d, skipped %d (quota), errors %d",
                        processed_count, skipped_count, error_count)

        except Exception as e:
            logger.error("Error in reprocess_stuck_messages: %s", e)

    # ------------------------------------------------------------------
    # Reprocess recent messages
    # ------------------------------------------------------------------

    async def reprocess_recent_messages(self, num_messages: int, force: bool = False, user_id: Optional[int] = None, channel_id: Optional[int] = None, stop_on_existing: bool = False) -> dict:
        logger.info("Starting reprocess_recent_messages: num_messages=%s, force=%s, user_id=%s", num_messages, force, user_id)

        db = mongodb.get_database()
        stats = {
            "total_processed": 0,
            "skipped": 0,
            "real_estate_ads": 0,
            "spam_filtered": 0,
            "not_real_estate": 0,
            "matched_filters": 0,
            "forwarded": 0,
            "errors": 0,
        }

        client = self.client_manager.client

        if channel_id:
            channels = [channel_id]
            logger.info("Using specific channel: %s", channel_id)
        else:
            monitored_channels = await self.client_manager._get_monitored_channels_new()
            channels = [c["channel_id"] for c in monitored_channels]
            logger.info("Using monitored channels: %s", channels)

        if not channels:
            logger.warning("No monitored channels found")
            return stats

        messages_to_fetch = num_messages * 10
        recent_messages = []

        for ch_id in channels:
            logger.info("Fetching messages from channel %s", ch_id)
            messages = []
            if not client:
                logger.error("Telegram client not initialized")
                continue

            async for message in client.iter_messages(int(ch_id), limit=messages_to_fetch):
                messages.append(message)

            recent_messages.extend(messages)
            logger.info("Fetched %s messages from channel %s", len(messages), ch_id)

        recent_messages.sort(key=lambda x: x.date, reverse=True)
        grouped_messages = self._group_messages_by_grouped_id(recent_messages)
        logger.info("Grouped %s messages into %s groups", len(recent_messages), len(grouped_messages))

        group_items = list(grouped_messages.items())
        group_items.sort(key=lambda x: x[1][0].date, reverse=True)
        group_items = group_items[:num_messages]
        grouped_messages = dict(group_items)

        logger.info("Processing %s advertisements (requested: %s)", len(grouped_messages), num_messages)

        for group_id, group_messages in grouped_messages.items():
            logger.info("Processing advertisement %s with %s messages", group_id, len(group_messages))

            combined_text = ""
            for message in group_messages:
                if message.text:
                    combined_text += message.text + "\n"

            main_message = group_messages[0]
            main_message.text = combined_text.strip() if combined_text else ""

            if main_message.text:
                logger.info("Advertisement text: %s%s", main_message.text[:200], "..." if len(main_message.text) > 200 else "")
            else:
                logger.info("Advertisement %s has no text content", group_id)

            existing_post = await db.incoming_messages.find_one(
                {"id": main_message.id, "channel_id": main_message.chat_id}
            )

            if existing_post:
                current_status = existing_post.get("processing_status")
                if stop_on_existing and not force:
                    logger.info("Found existing message %s, stopping processing (stop_on_existing=True)", main_message.id)
                    break

                if force:
                    logger.info("Force reprocessing message %s (current status: %s)", main_message.id, current_status)
                    await db.incoming_messages.update_one(
                        {"id": main_message.id, "channel_id": main_message.chat_id},
                        {"$set": {"processing_status": IncomingMessageStatus.PENDING}},
                    )
                else:
                    if current_status == IncomingMessageStatus.DELETED:
                        logger.debug("Skipping message %s - status is DELETED", main_message.id)
                        stats["skipped"] += 1
                        continue

                    if current_status in [
                        IncomingMessageStatus.PARSED,
                        IncomingMessageStatus.FORWARDED,
                        IncomingMessageStatus.SPAM_FILTERED,
                        IncomingMessageStatus.NOT_REAL_ESTATE,
                        IncomingMessageStatus.MEDIA_ONLY,
                    ]:
                        stats["skipped"] += 1
                        continue
                    elif current_status == IncomingMessageStatus.ERROR:
                        parsing_errors = existing_post.get("parsing_errors", [])
                        is_quota_error = any(
                            "quota" in str(error).lower() or "insufficient" in str(error).lower()
                            for error in parsing_errors
                        )
                        if is_quota_error and llm_quota_service.is_quota_exceeded():
                            logger.info("Skipping message %s with quota error status (quota still exceeded)", main_message.id)
                            stats["skipped"] += 1
                            continue
                        logger.info("Message %s had error status, reprocessing", main_message.id)
                        await db.incoming_messages.update_one(
                            {"id": main_message.id, "channel_id": main_message.chat_id},
                            {"$set": {"processing_status": IncomingMessageStatus.PENDING}},
                        )
                    else:
                        logger.info("Message %s has status %s, reprocessing", main_message.id, current_status)
                        await db.incoming_messages.update_one(
                            {"id": main_message.id, "channel_id": main_message.chat_id},
                            {"$set": {"processing_status": IncomingMessageStatus.PENDING}},
                        )
            else:
                logger.info("Message %s not found in database, processing for first time", main_message.id)

            await self._process_message(main_message, force, user_id=user_id)

            if not self.validator._is_media_only_message(main_message):
                stats["total_processed"] += 1

            post = await db.incoming_messages.find_one({"id": main_message.id, "channel_id": main_message.chat_id})
            if post:
                post_status = post.get("processing_status")
                if post_status == IncomingMessageStatus.SPAM_FILTERED:
                    stats["spam_filtered"] += 1
                elif post_status == IncomingMessageStatus.MEDIA_ONLY:
                    pass
                elif post_status == IncomingMessageStatus.NOT_REAL_ESTATE:
                    stats["not_real_estate"] += 1
                elif post_status in [IncomingMessageStatus.PARSED, IncomingMessageStatus.FORWARDED]:
                    stats["real_estate_ads"] += 1

                    if user_id:
                        real_estate_ad = await db.real_estate_ads.find_one({
                            "original_post_id": main_message.id,
                            "original_channel_id": main_message.chat_id
                        })
                        if real_estate_ad:
                            match_count = await db.user_filter_matches.count_documents({
                                "user_id": user_id,
                                "real_estate_ad_id": str(real_estate_ad["_id"])
                            })
                            if match_count > 0:
                                stats["matched_filters"] += 1

                            forwarded_count = await db.outgoing_posts.count_documents({
                                "sent_to": str(user_id),
                                "real_estate_ad_id": str(real_estate_ad["_id"])
                            })
                            if forwarded_count > 0:
                                stats["forwarded"] += 1
                    else:
                        if post_status == IncomingMessageStatus.FORWARDED:
                            stats["forwarded"] += 1
                elif post_status == IncomingMessageStatus.ERROR:
                    stats["errors"] += 1

        logger.info("Reprocessing completed: %s", stats)
        return stats

    # ------------------------------------------------------------------
    # Refilter ads
    # ------------------------------------------------------------------

    async def refilter_ads(self, count: int, user_id: Optional[int] = None) -> dict:
        try:
            logger.info("Starting refilter for %s ads", count)
            db = mongodb.get_database()

            real_estate_ads_cursor = db.real_estate_ads.find().sort("_id", -1).limit(count)
            ads_list = []
            async for ad_doc in real_estate_ads_cursor:
                ads_list.append(ad_doc)

            logger.info("Found %s ads to refilter", len(ads_list))

            total_checked = 0
            forwarded = 0
            errors = 0

            user_filters_cursor = db.simple_filters.find({"is_active": True})
            user_filters = {}
            async for filter_doc in user_filters_cursor:
                filter_user_id = filter_doc.get("user_id")
                if filter_user_id not in user_filters:
                    user_filters[filter_user_id] = []
                user_filters[filter_user_id].append(filter_doc)

            logger.info("Found filters for %s users", len(user_filters))

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

            for ad_doc in ads_list:
                try:
                    total_checked += 1
                    ad = RealEstateAd(**ad_doc)

                    if ad.processing_status == RealEstateAdStatus.FORWARDED:
                        logger.info("Skipping ad %s - already forwarded", ad.original_post_id)
                        continue

                    for uid, user_filter_docs in user_filters.items():
                        try:
                            filter_result = await self.filter_service.check_filters(ad, uid)
                            matching_filters = filter_result.get("matching_filters", [])
                            filter_details = filter_result.get("filter_details", {})

                            logger.info("Ad %s (rooms=%s, price=%s %s) checked against user %s filters: %d matches",
                                        ad.original_post_id, ad.rooms_count, ad.price, ad.currency, uid, len(matching_filters))

                            if matching_filters:
                                first_filter_id = matching_filters[0]
                                filter_name = filter_details.get(first_filter_id, {}).get("name", "unknown")
                                await self.forwarder._forward_post(None, ad, first_filter_id, filter_name, uid)
                                forwarded += 1
                                logger.info("Ad %s forwarded to user %s with filter %s",
                                            ad.original_post_id, uid, filter_name)
                            else:
                                logger.info("Ad %s did not match any filters for user %s",
                                            ad.original_post_id, uid)

                        except Exception as e:
                            logger.error("Error checking filters for ad %s, user %s: %s", ad.original_post_id, uid, e)
                            errors += 1

                except Exception as e:
                    logger.error("Error processing ad %s: %s", ad_doc.get("_id"), e)
                    errors += 1

            result = {
                "total_checked": total_checked,
                "forwarded": forwarded,
                "errors": errors,
            }
            logger.info("Refilter completed: %s", result)
            return result

        except Exception as e:
            logger.error("Error in refilter_ads: %s", e)
            raise
