#!/usr/bin/env python3
"""
Script to get information about Telegram channels and subchannels
"""
import asyncio
import os
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from app.core.config import settings

async def get_channel_info():
    """Get information about channels"""
    
    # Create client
    client = TelegramClient(
        settings.TELEGRAM_SESSION_NAME,
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH
    )
    
    try:
        await client.start(phone=settings.TELEGRAM_PHONE)
        print("Connected to Telegram!")
        
        # Get current monitored channel
        current_channel_id = int(settings.TELEGRAM_MONITORED_CHANNELS)
        print(f"\nCurrent monitored channel ID: {current_channel_id}")
        
        # Get channel info
        try:
            channel = await client.get_entity(current_channel_id)
            print(f"Channel title: {channel.title}")
            print(f"Channel username: @{channel.username}" if hasattr(channel, 'username') and channel.username else "No username")
            print(f"Channel type: {type(channel).__name__}")
            
        except Exception as e:
            print(f"Error getting channel info: {e}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(get_channel_info())
