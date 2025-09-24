import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

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
logging.getLogger("httpx").setLevel(logging.WARNING)
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

        yield

    finally:
        # Shutdown
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

    # Check Telegram bot status (simplified)
    try:
        telegram_service = get_telegram_service()
        if telegram_service:
            health_status["components"]["telegram_bot"] = "initialized"
        else:
            health_status["components"]["telegram_bot"] = "not_initialized"
    except Exception as e:
        health_status["components"]["telegram_bot"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    return health_status
