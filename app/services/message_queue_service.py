"""
Service for managing message processing queue with Redis
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
import redis.asyncio as redis

from app.models.message_queue import QueuedMessage, ProcessingStatus, ProcessingResult
from app.models.telegram import RealEstateAd
from app.services.llm_service import LLMService
from app.services.simple_filter_service import SimpleFilterService
from app.core.config import settings

logger = logging.getLogger(__name__)


class MessageQueueService:
    """Service for managing message processing queue"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.llm_service = LLMService()
        self.filter_service = SimpleFilterService()
        self.is_processing = False
    
    async def get_redis_client(self) -> redis.Redis:
        """Get Redis client connection"""
        if not self.redis_client:
            self.redis_client = redis.from_url(settings.REDIS_URL)
        return self.redis_client
    
    async def add_message_to_queue(
        self, 
        post_id: int, 
        channel_id: int, 
        message: str, 
        url: Optional[str] = None
    ) -> str:
        """Add message to processing queue"""
        try:
            redis_client = await self.get_redis_client()
            
            queued_message = QueuedMessage(
                original_post_id=post_id,
                original_channel_id=channel_id,
                original_message=message,
                original_url=url
            )
            
            # Generate unique ID
            message_id = f"{channel_id}_{post_id}_{int(datetime.utcnow().timestamp())}"
            queued_message.id = message_id
            
            # Store in Redis with TTL (24 hours)
            await redis_client.setex(
                f"queue:message:{message_id}",
                86400,  # 24 hours
                queued_message.model_dump_json()
            )
            
            # Add to processing queue
            await redis_client.lpush("queue:processing", message_id)
            
            logger.info(f"Added message {message_id} to processing queue")
            return message_id
            
        except Exception as e:
            logger.error(f"Error adding message to queue: {e}")
            raise
    
    async def get_next_message(self) -> Optional[QueuedMessage]:
        """Get next message from processing queue"""
        try:
            redis_client = await self.get_redis_client()
            
            # Blocking pop with timeout
            result = await redis_client.brpop("queue:processing", timeout=1)
            if not result:
                return None
            
            message_id = result[1].decode('utf-8')
            
            # Get message data
            message_data = await redis_client.get(f"queue:message:{message_id}")
            if not message_data:
                logger.warning(f"Message {message_id} not found in Redis")
                return None
            
            return QueuedMessage.model_validate_json(message_data)
            
        except Exception as e:
            logger.error(f"Error getting next message: {e}")
            return None
    
    async def update_message_status(
        self, 
        message_id: str, 
        status: ProcessingStatus,
        errors: Optional[List[str]] = None
    ) -> bool:
        """Update message processing status"""
        try:
            redis_client = await self.get_redis_client()
            
            # Get current message
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
            
            # Update in Redis
            await redis_client.setex(
                f"queue:message:{message_id}",
                86400,
                message.model_dump_json()
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating message status: {e}")
            return False
    
    async def process_message(self, message: QueuedMessage) -> ProcessingResult:
        """Process a single message through LLM and filters"""
        start_time = datetime.utcnow()
        message_id = message.id
        
        try:
            # Update status to processing
            await self.update_message_status(message_id, ProcessingStatus.PROCESSING)
            
            # Process with LLM
            real_estate_ad = await self.llm_service.parse_with_llm(
                message.original_message,
                message.original_post_id,
                message.original_channel_id
            )
            
            if not real_estate_ad:
                # Not a real estate ad, skip
                await self.update_message_status(message_id, ProcessingStatus.SKIPPED)
                return ProcessingResult(
                    success=True,
                    message_id=message_id,
                    processing_time_seconds=(datetime.utcnow() - start_time).total_seconds()
                )
            
            # Check filters
            filter_result = await self.filter_service.check_filters(real_estate_ad)
            
            # Update real estate ad with filter results
            real_estate_ad.matched_filters = filter_result["matching_filters"]
            real_estate_ad.should_forward = filter_result["should_forward"]
            real_estate_ad.processing_status = "completed"
            real_estate_ad.llm_processed = True
            
            # Save to database (this is already done in LLM service)
            # The RealEstateAd is saved in _save_real_estate_ad method
            
            # Update message status
            await self.update_message_status(message_id, ProcessingStatus.COMPLETED)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return ProcessingResult(
                success=True,
                message_id=message_id,
                real_estate_ad_id=str(real_estate_ad.id) if real_estate_ad.id else None,
                llm_cost=real_estate_ad.llm_cost,
                processing_time_seconds=processing_time
            )
            
        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}")
            
            # Update status to failed
            await self.update_message_status(
                message_id, 
                ProcessingStatus.FAILED, 
                errors=[str(e)]
            )
            
            return ProcessingResult(
                success=False,
                message_id=message_id,
                errors=[str(e)],
                processing_time_seconds=(datetime.utcnow() - start_time).total_seconds()
            )
    
    async def start_processing_worker(self):
        """Start background worker to process messages"""
        if self.is_processing:
            logger.warning("Processing worker is already running")
            return
        
        self.is_processing = True
        logger.info("Starting message processing worker")
        
        try:
            while self.is_processing:
                try:
                    # Get next message
                    message = await self.get_next_message()
                    if not message:
                        # No messages, wait a bit
                        await asyncio.sleep(1)
                        continue
                    
                    # Process message
                    result = await self.process_message(message)
                    
                    if result.success:
                        logger.info(f"Successfully processed message {result.message_id}")
                    else:
                        logger.error(f"Failed to process message {result.message_id}: {result.errors}")
                
                except Exception as e:
                    logger.error(f"Error in processing worker: {e}")
                    await asyncio.sleep(5)  # Wait before retrying
                    
        except asyncio.CancelledError:
            logger.info("Message processing worker stopped")
        finally:
            self.is_processing = False
    
    async def stop_processing_worker(self):
        """Stop background worker"""
        self.is_processing = False
        logger.info("Stopping message processing worker")
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue processing statistics"""
        try:
            redis_client = await self.get_redis_client()
            
            # Get queue length
            queue_length = await redis_client.llen("queue:processing")
            
            # Get processing stats
            processing_keys = await redis_client.keys("queue:message:*")
            total_messages = len(processing_keys)
            
            # Count by status
            status_counts = {}
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
                "worker_running": self.is_processing
            }
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {
                "queue_length": 0,
                "total_messages": 0,
                "status_counts": {},
                "worker_running": False,
                "error": str(e)
            }
