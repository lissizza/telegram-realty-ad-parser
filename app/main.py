import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

# Custom filter to suppress verbose NetworkError tracebacks
class NetworkErrorFilter(logging.Filter):
    """Filter to suppress verbose NetworkError tracebacks from telegram library"""
    
    def filter(self, record):
        # Check if this is a NetworkError or ConnectionError from telegram
        is_network_error = False
        
        # Check exc_info
        if record.exc_info and record.exc_info[0]:
            exc_type = record.exc_info[0]
            exc_name = exc_type.__name__ if hasattr(exc_type, '__name__') else str(exc_type)
            
            if 'NetworkError' in exc_name or 'ConnectError' in exc_name or 'OSError' in exc_name:
                is_network_error = True
        
        # Also check message text for network errors
        msg_text = str(record.msg) if record.msg else ""
        if 'NetworkError' in msg_text or 'ConnectError' in msg_text or 'No address associated with hostname' in msg_text:
            is_network_error = True
        
        # Suppress full traceback for network errors
        if is_network_error:
            # Convert to simple error message without traceback
            if record.exc_info and record.exc_info[1]:
                error_msg = str(record.exc_info[1])
                # Extract just the error message, not the full traceback
                record.msg = f"Network error: {error_msg}"
            elif 'NetworkError' in msg_text or 'ConnectError' in msg_text:
                # Extract error message from text
                if 'No address associated with hostname' in msg_text:
                    record.msg = "Network error: No address associated with hostname"
                else:
                    record.msg = f"Network error: {msg_text[:200]}"  # Truncate long messages
            
            record.exc_info = None
            record.exc_text = None
        
        return True

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Suppress DEBUG logs from external libraries
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("telethon.telegram_client").setLevel(logging.WARNING)
logging.getLogger("telethon.network").setLevel(logging.WARNING)
logging.getLogger("telethon.crypto").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Add filter to telegram loggers to suppress verbose NetworkError tracebacks
network_error_filter = NetworkErrorFilter()
logging.getLogger("telegram.ext").addFilter(network_error_filter)
logging.getLogger("telegram").addFilter(network_error_filter)
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.init_db import init_database
from app.db.mongodb import mongodb
from app.services import get_telegram_service, set_telegram_service
from app.services.telegram_service import TelegramService
from app.telegram_bot import telegram_bot

logger = logging.getLogger(__name__)
logger.info("Main module loaded")

# Global variables for health check monitoring
_last_healthy_time = None
_unhealthy_start_time = None
_MAX_UNHEALTHY_DURATION = 600  # 10 minutes in seconds
_shutdown_scheduled = False


async def _schedule_forced_shutdown(delay_seconds: float = 1.0) -> None:
    """Schedule forced process shutdown to trigger container restart."""
    await asyncio.sleep(delay_seconds)
    logger.error("Forcing process exit to trigger container restart")
    os._exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application lifespan")
    await mongodb.connect_to_mongo()
    await init_database()
    logger.info("Database initialized")

    # Start Telegram services
    telegram_service = TelegramService()
    set_telegram_service(telegram_service)

    # Initialize notification service with bot
    telegram_service.set_notification_service(telegram_bot)
    
    # Update global instance with notification service
    global_telegram_service = get_telegram_service()
    global_telegram_service.set_notification_service(telegram_bot)
    
    # Initialize admin notification service
    from app.services.admin_notification_service import admin_notification_service
    from app.services.notification_service import TelegramNotificationService
    from app.services.llm_quota_service import llm_quota_service
    from app.services.llm_service import LLMService
    
    # Create LLM service instance and inject it into quota service
    llm_service = LLMService()
    logger.info("LLM Service initialized: provider=%s, model=%s, base_url=%s", 
                settings.LLM_PROVIDER, settings.LLM_MODEL, settings.LLM_BASE_URL or "default")
    llm_quota_service.set_llm_service(llm_service)
    
    admin_notification_service.set_notification_service(TelegramNotificationService(telegram_bot))
    bot_task = None
    parsing_task = None

    try:
        # Start Telegram bot
        if settings.TELEGRAM_BOT_TOKEN:
            logger.info(f"Starting Telegram bot with token: {settings.TELEGRAM_BOT_TOKEN[:10]}...")
            bot_task = asyncio.create_task(telegram_bot.start_bot())
            logger.info("Telegram bot task created")

        # Start parsing service - monitor channels for real estate ads
        logger.info(
            f"Checking Telegram API credentials: API_ID={settings.TELEGRAM_API_ID}, API_HASH={settings.TELEGRAM_API_HASH[:10] if settings.TELEGRAM_API_HASH else None}"
        )
        if settings.TELEGRAM_API_ID and settings.TELEGRAM_API_HASH:
            logger.info(f"Starting Telegram parsing service with API_ID: {settings.TELEGRAM_API_ID}")
            try:
                parsing_task = asyncio.create_task(telegram_service.start_monitoring())
                logger.info("Telegram parsing service task created")
            except Exception as e:
                logger.error(f"Failed to start Telegram parsing service: {e}")
                parsing_task = None
        else:
            logger.warning("Telegram API credentials not found, skipping parsing service")

        # Start periodic LLM balance checking
        await llm_quota_service.start_periodic_balance_check()
        logger.info("Started periodic LLM balance check (interval: 15 minutes)")

        yield

    finally:
        # Shutdown
        from app.services.llm_quota_service import llm_quota_service
        await llm_quota_service.stop_periodic_balance_check()
        logger.info("Stopped periodic LLM balance check")
        
        if bot_task:
            await telegram_bot.stop_bot()
            bot_task.cancel()
            logger.info("Telegram bot stopped")

        if parsing_task:
            await telegram_service.stop_monitoring()
            parsing_task.cancel()
            logger.info("Telegram parsing service stopped")

        await mongodb.close_mongo_connection()


app = FastAPI(
    title="Telegram Bot API",
    description="API for Telegram bot that analyzes and forwards posts " "based on filters",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Export app for use in other modules
__all__ = ["app"]


@app.get("/")
async def root():
    return {"message": "Telegram Bot API is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint that verifies system components"""
    global _last_healthy_time, _unhealthy_start_time, _shutdown_scheduled
    
    health_status = {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat(), "components": {}}

    # Check MongoDB connection
    try:
        await mongodb.client.admin.command("ping")
        health_status["components"]["mongodb"] = "healthy"
    except Exception as e:
        health_status["components"]["mongodb"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    # Check Redis connection
    try:
        import redis.asyncio as redis

        redis_client = redis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        await redis_client.close()
        health_status["components"]["redis"] = "healthy"
    except Exception as e:
        health_status["components"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    # Check Telegram bot status
    try:
        telegram_service = get_telegram_service()
        if telegram_service:
            # Check if TelegramService is healthy
            if telegram_service.is_connection_healthy():
                health_status["components"]["telegram_bot"] = "healthy"
                health_status["components"]["telegram_service"] = "connected"
            else:
                health_status["components"]["telegram_bot"] = "unhealthy"
                health_status["components"]["telegram_service"] = "disconnected"
                health_status["status"] = "unhealthy"
            
            # Add detailed connection status
            health_status["components"]["telegram_details"] = telegram_service.get_connection_status()
        else:
            health_status["components"]["telegram_bot"] = "not_initialized"
            health_status["components"]["telegram_service"] = "not_initialized"
            health_status["status"] = "unhealthy"
    except Exception as e:
        health_status["components"]["telegram_bot"] = f"unhealthy: {str(e)}"
        health_status["components"]["telegram_service"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    # Return appropriate HTTP status code
    if health_status["status"] == "unhealthy":
        # Track unhealthy duration
        current_time = datetime.now(timezone.utc)
        if _unhealthy_start_time is None:
            _unhealthy_start_time = current_time
            logger.warning("System became unhealthy, starting timer")
        
        unhealthy_duration = (current_time - _unhealthy_start_time).total_seconds()
        
        # If system has been unhealthy for too long, exit to trigger container restart
        if unhealthy_duration > _MAX_UNHEALTHY_DURATION:
            logger.error(
                "System has been unhealthy for %d seconds (max: %d), exiting to trigger container restart",
                unhealthy_duration, _MAX_UNHEALTHY_DURATION
            )
            global _shutdown_scheduled
            if not _shutdown_scheduled:
                _shutdown_scheduled = True
                asyncio.create_task(_schedule_forced_shutdown())
        
        _last_healthy_time = None
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=health_status)
    else:
        # System is healthy, reset unhealthy timer
        if _unhealthy_start_time is not None:
            unhealthy_duration = (datetime.now(timezone.utc) - _unhealthy_start_time).total_seconds()
            logger.info("System recovered, was unhealthy for %d seconds", unhealthy_duration)
            _unhealthy_start_time = None
        if _shutdown_scheduled:
            _shutdown_scheduled = False
        
        _last_healthy_time = datetime.now(timezone.utc)
    
    return health_status
