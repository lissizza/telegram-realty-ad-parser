"""
Service for managing LLM quota status and balance checking
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, TYPE_CHECKING

from app.db.mongodb import mongodb
from app.exceptions import LLMQuotaExceededError

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class LLMQuotaService:
    """Service for managing LLM quota status and periodic balance checking"""
    
    def __init__(self, llm_service: Optional["LLMService"] = None):
        self._llm_service = llm_service
        self._quota_exceeded = False
        self._last_quota_error_time: Optional[datetime] = None
        self._last_balance_check_time: Optional[datetime] = None
        self._balance_check_interval = timedelta(minutes=15)  # Check balance every 15 minutes
        self._balance_check_task: Optional[asyncio.Task] = None
        
    def set_llm_service(self, llm_service: "LLMService") -> None:
        """Set LLM service instance (dependency injection)"""
        self._llm_service = llm_service
        
    def _get_llm_service(self) -> "LLMService":
        """Get LLM service instance"""
        if self._llm_service is None:
            raise RuntimeError("LLM service not initialized. Call set_llm_service() first.")
        return self._llm_service
        
    def set_quota_exceeded(self, error_time: Optional[datetime] = None) -> None:
        """Set quota exceeded flag"""
        self._quota_exceeded = True
        self._last_quota_error_time = error_time or datetime.now(timezone.utc)
        logger.warning("LLM quota exceeded flag set at %s", self._last_quota_error_time)
        
    def clear_quota_exceeded(self) -> None:
        """Clear quota exceeded flag"""
        if self._quota_exceeded:
            logger.info("LLM quota exceeded flag cleared - balance restored")
        self._quota_exceeded = False
        self._last_quota_error_time = None
        
    def is_quota_exceeded(self) -> bool:
        """Check if quota is currently exceeded"""
        return self._quota_exceeded
        
    async def check_balance(self) -> bool:
        """
        Check LLM balance by making a test request
        Returns True if balance is available, False otherwise
        """
        try:
            logger.info("Checking LLM balance with test request...")
            
            # Make a minimal test request to check if API is working
            test_prompt = "Test"
            llm_service = self._get_llm_service()
            try:
                result = await llm_service.parse_with_llm(
                    text=test_prompt,
                    post_id=0,  # Dummy ID for test
                    channel_id=0,  # Dummy ID for test
                    incoming_message_id=None,
                    topic_id=None,
                )
                
                # If we got here without exception, balance is available
                self._last_balance_check_time = datetime.now(timezone.utc)
                if self._quota_exceeded:
                    logger.info("✅ LLM balance check successful - quota restored! Processing will resume.")
                    self.clear_quota_exceeded()
                    
                    # Automatically trigger reprocessing of stuck messages
                    try:
                        from app.services import get_telegram_service
                        telegram_service = get_telegram_service()
                        logger.info("Automatically triggering reprocessing of stuck messages after balance restore")
                        await telegram_service._reprocess_stuck_messages()
                        logger.info("✅ Successfully triggered reprocessing of stuck messages")
                    except Exception as e:
                        logger.error("Error automatically reprocessing stuck messages after balance restore: %s", e)
                else:
                    logger.debug("✅ LLM balance check successful - quota available")
                return True
            except LLMQuotaExceededError as e:
                # Quota exceeded error - this is the only case when we set the flag
                logger.warning("❌ LLM balance check failed - quota still exceeded: %s", e)
                self.set_quota_exceeded()
                return False
            
        except Exception as e:
            # Check if it's a quota error
            error_str = str(e).lower()
            if "quota" in error_str or "insufficient" in error_str or "429" in error_str:
                logger.warning("❌ LLM balance check failed - quota still exceeded: %s", e)
                self.set_quota_exceeded()
                return False
            else:
                # Other errors (network, etc.) - don't change quota status
                logger.warning("⚠️ LLM balance check failed with non-quota error: %s", e)
                return False
                
    async def start_periodic_balance_check(self) -> None:
        """Start periodic balance checking task"""
        if self._balance_check_task and not self._balance_check_task.done():
            logger.warning("Balance check task already running")
            return
            
        logger.info("Starting periodic LLM balance check (interval: %s)", self._balance_check_interval)
        self._balance_check_task = asyncio.create_task(self._periodic_balance_check_loop())
        
    async def stop_periodic_balance_check(self) -> None:
        """Stop periodic balance checking task"""
        if self._balance_check_task:
            self._balance_check_task.cancel()
            try:
                await self._balance_check_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped periodic LLM balance check")
            
    async def _periodic_balance_check_loop(self) -> None:
        """Periodic balance check loop"""
        try:
            while True:
                # Wait for check interval
                await asyncio.sleep(self._balance_check_interval.total_seconds())
                
                # Only check if quota is currently exceeded
                if self._quota_exceeded:
                    logger.info("Periodic balance check triggered (quota exceeded, interval: %s)", self._balance_check_interval)
                    balance_available = await self.check_balance()
                    if balance_available:
                        logger.info("✅ Balance restored - processing will resume automatically")
                    else:
                        logger.info("❌ Balance check: quota still exceeded, next check in %s", self._balance_check_interval)
                else:
                    logger.debug("Periodic balance check skipped (quota not exceeded, interval: %s)", self._balance_check_interval)
                    
        except asyncio.CancelledError:
            logger.info("Periodic balance check loop cancelled")
            raise
        except Exception as e:
            logger.error("Error in periodic balance check loop: %s", e)
            
    def get_status(self) -> dict:
        """Get current quota status"""
        return {
            "quota_exceeded": self._quota_exceeded,
            "last_quota_error_time": self._last_quota_error_time.isoformat() if self._last_quota_error_time else None,
            "last_balance_check_time": self._last_balance_check_time.isoformat() if self._last_balance_check_time else None,
            "balance_check_interval_minutes": self._balance_check_interval.total_seconds() / 60,
        }


# Global instance
llm_quota_service = LLMQuotaService()

