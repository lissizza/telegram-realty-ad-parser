#!/usr/bin/env python3
"""
Simple script to create Telegram session
"""
import asyncio
from telethon import TelegramClient
from app.core.config import settings

async def create_session():
    """Create Telegram session"""
    
    # Create client
    client = TelegramClient(
        settings.TELEGRAM_SESSION_NAME,
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH
    )
    
    try:
        await client.start(phone=settings.TELEGRAM_PHONE)
        print("✅ Session created successfully!")
        print(f"📱 Phone: {settings.TELEGRAM_PHONE}")
        print(f"🔑 Session file: {settings.TELEGRAM_SESSION_NAME}.session")
        
    except Exception as e:
        print(f"❌ Error creating session: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(create_session())
