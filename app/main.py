from contextlib import asynccontextmanager
import asyncio
import logging

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

from app.core.config import settings
from app.api.v1.api import api_router
from app.db.mongodb import mongodb
from app.db.init_db import init_database
from app.services.telegram_service import TelegramService
from app.telegram_bot import telegram_bot

# Global telegram service instance
telegram_service = None

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
    global telegram_service
    telegram_service = TelegramService()
    bot_task = None
    parsing_task = None
    
    try:
        # Start Telegram bot
        if settings.TELEGRAM_BOT_TOKEN:
            logger.info(f"Starting Telegram bot with token: {settings.TELEGRAM_BOT_TOKEN[:10]}...")
            bot_task = asyncio.create_task(telegram_bot.start_bot())
            logger.info("Telegram bot task created")
        
        # Start parsing service - monitor channels for real estate ads
        logger.info(f"Checking Telegram API credentials: API_ID={settings.TELEGRAM_API_ID}, API_HASH={settings.TELEGRAM_API_HASH[:10] if settings.TELEGRAM_API_HASH else None}")
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
    description="API for Telegram bot that analyzes and forwards posts "
    "based on filters",
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

# Export telegram_service for use in other modules
__all__ = ["app", "telegram_service"]


@app.get("/")
async def root():
    return {"message": "Telegram Bot API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"} 