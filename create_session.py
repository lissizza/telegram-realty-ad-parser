#!/usr/bin/env python3
"""
Simple script to create Telegram session
"""
import asyncio
import os
from telethon import TelegramClient
from dotenv import load_dotenv

async def create_session():
    """Create Telegram session"""
    
    # Load environment variables
    load_dotenv()
    
    api_id = int(os.getenv('TELEGRAM_API_ID'))
    api_hash = os.getenv('TELEGRAM_API_HASH')
    phone = os.getenv('TELEGRAM_PHONE')
    session_name = os.getenv('TELEGRAM_SESSION_NAME', 'telegram_bot_session')
    
    # Create client
    client = TelegramClient(session_name, api_id, api_hash)
    
    try:
        await client.start(phone=phone)
        print("✅ Session created successfully!")
        print(f"📱 Phone: {phone}")
        print(f"🔑 Session file: {session_name}.session")
        
    except Exception as e:
        print(f"❌ Error creating session: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(create_session())



