"""
Service for managing message processing queue with Redis
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from app.core.config import settings
from app.models.message_queue import ProcessingResult, ProcessingStatus, QueuedMessage
from app.services.llm_service import LLMService
from app.services.simple_filter_service import SimpleFilterService

logger = logging.getLogger(__name__)


class MessageQueueService:
    """Service for managing message processing queue"""

    def __init__(self) -> None:
        self.redis_client: Optional[redis.Redis] = None
        self.llm_service = LLMService()
        self.filter_service = SimpleFilterService()
        self.is_processing = False

    async def get_redis_client(self) -> redis.Redis:
        """Get Redis client connection"""
        if not self.redis_client:
            self.redis_client = redis.from_url(settings.REDIS_URL)
            if not self.redis_client:
                raise RuntimeError("Failed to create Redis client")
        return self.redis_client

    async def add_message_to_queue(self, post_id: int, channel_id: int, message: str, url: Optional[str] = None) -> str:
        """Add message to processing queue"""
        try:
            redis_client = await self.get_redis_client()

            queued_message = QueuedMessage(
                original_post_id=post_id, original_channel_id=channel_id, original_message=message, original_url=url
            )

            # Generate unique ID
            message_id = f"{channel_id}_{post_id}_{int(datetime.utcnow().timestamp())}"
            queued_message.id = message_id

            # Store in Redis with TTL (24 hours)
            await redis_client.setex(f"queue:message:{message_id}", 86400, queued_message.model_dump_json())  # 24 hours

            # Add to processing queue
            await redis_client.lpush("queue:processing", message_id)  # type: ignore

            logger.info("Added message %s to processing queue", message_id)
            return message_id

        except Exception as e:
            logger.error("Error adding message to queue: %s", e)
            raise

    async def get_next_message(self) -> Optional[QueuedMessage]:
        """Get next message from processing queue"""
        try:
            redis_client = await self.get_redis_client()

            # Blocking pop with timeout
            result = await redis_client.brpop(["queue:processing"], timeout=1)  # type: ignore
            if not result:
                return None

            message_id = result[1].decode("utf-8") if isinstance(result[1], bytes) else str(result[1])

            message_data = await redis_client.get(f"queue:message:{message_id}")
            if not message_data:
                logger.warning("Message %s not found in Redis", message_id)
                return None

            return QueuedMessage.model_validate_json(message_data)

        except Exception as e:
            logger.error("Error getting next message: %s", e)
            return None

    async def update_message_status(
        self, message_id: str, status: ProcessingStatus, errors: Optional[List[str]] = None
    ) -> bool:
        """Update message processing status"""
        try:
            redis_client = await self.get_redis_client()

            message_data = await redis_client.get(f"queue:message:{message_id}")
            if not message_data:
                return False

            message = QueuedMessage.model_validate_json(message_data)
            message.status = status
            message.updated_at = datetime.utcnow()

            if status == ProcessingStatus.PROCESSING:
                message.processing_started_at = datetime.utcnow()
            elif status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.SKIPPED]:
                message.processing_completed_at = datetime.utcnow()

            if errors:
                message.processing_errors.extend(errors)

            await redis_client.setex(f"queue:message:{message_id}", 86400, message.model_dump_json())

            return True

        except Exception as e:
            logger.error("Error updating message status: %s", e)
            return False

    async def process_message(self, message: QueuedMessage) -> ProcessingResult:
        """Process a single message through LLM and filters"""
        start_time = datetime.utcnow()
        message_id = message.id
        if not message_id:
            raise ValueError("Message ID is required")

        try:
            await self.update_message_status(message_id, ProcessingStatus.PROCESSING)

            real_estate_ad = await self.llm_service.parse_with_llm(
                message.original_message, message.original_post_id, message.original_channel_id
            )

            if not real_estate_ad:
                await self.update_message_status(message_id, ProcessingStatus.SKIPPED)
                return ProcessingResult(
                    success=True,
                    message_id=message_id,
                    processing_time_seconds=(datetime.utcnow() - start_time).total_seconds(),
                )

            filter_result = await self.filter_service.check_filters(real_estate_ad)

            real_estate_ad.matched_filters = filter_result["matching_filters"]
            real_estate_ad.should_forward = filter_result["should_forward"]
            real_estate_ad.processing_status = "completed"
            real_estate_ad.llm_processed = True

            await self.update_message_status(message_id, ProcessingStatus.COMPLETED)

            processing_time = (datetime.utcnow() - start_time).total_seconds()

            return ProcessingResult(
                success=True,
                message_id=message_id,
                real_estate_ad_id=str(real_estate_ad.id) if real_estate_ad.id else None,
                llm_cost=real_estate_ad.llm_cost,
                processing_time_seconds=processing_time,
            )

        except Exception as e:
            logger.error("Error processing message %s: %s", message_id, e)

            await self.update_message_status(message_id, ProcessingStatus.FAILED, errors=[str(e)])

            return ProcessingResult(
                success=False,
                message_id=message_id,
                errors=[str(e)],
                processing_time_seconds=(datetime.utcnow() - start_time).total_seconds(),
            )

    async def start_processing_worker(self) -> None:
        """Start background worker to process messages"""
        if self.is_processing:
            logger.warning("Processing worker is already running")
            return

        self.is_processing = True
        logger.info("Starting message processing worker")

        try:
            while self.is_processing:
                try:
                    message = await self.get_next_message()
                    if not message:
                        await asyncio.sleep(1)
                        continue

                    result = await self.process_message(message)

                    if result.success:
                        logger.info("Successfully processed message %s", result.message_id)
                    else:
                        logger.error("Failed to process message %s: %s", result.message_id, result.errors)

                except Exception as e:
                    logger.error("Error in processing worker: %s", e)
                    await asyncio.sleep(5)

        except asyncio.CancelledError:
            logger.info("Message processing worker stopped")
        finally:
            self.is_processing = False

    async def stop_processing_worker(self) -> None:
        """Stop background worker"""
        self.is_processing = False
        logger.info("Stopping message processing worker")

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue processing statistics"""
        try:
            redis_client = await self.get_redis_client()

            queue_length = int(await redis_client.llen("queue:processing"))  # type: ignore

            processing_keys = await redis_client.keys("queue:message:*")
            total_messages = len(processing_keys)

            status_counts: Dict[str, int] = {}
            for key in processing_keys:
                message_data = await redis_client.get(key)
                if message_data:
                    message = QueuedMessage.model_validate_json(message_data)
                    status = message.status.value
                    status_counts[status] = status_counts.get(status, 0) + 1

            return {
                "queue_length": queue_length,
                "total_messages": total_messages,
                "status_counts": status_counts,
                "worker_running": self.is_processing,
            }

        except Exception as e:
            logger.error("Error getting queue stats: %s", e)
            return {
                "queue_length": 0,
                "total_messages": 0,
                "status_counts": {},
                "worker_running": False,
                "error": str(e),
            }
