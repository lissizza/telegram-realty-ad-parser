#!/usr/bin/env python3
"""
Script to get information about Telegram channels and subchannels
"""
import asyncio
import os
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

async def get_channel_info():
    """Get information about channels"""
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    api_id = int(os.getenv('TELEGRAM_API_ID'))
    api_hash = os.getenv('TELEGRAM_API_HASH')
    phone = os.getenv('TELEGRAM_PHONE')
    session_name = os.getenv('TELEGRAM_SESSION_NAME', 'telegram_bot_session')
    
    # Create client
    client = TelegramClient(session_name, api_id, api_hash)
    
    try:
        await client.start(phone=phone)
        print("Connected to Telegram!")
        
        # Get current monitored channel
        current_channel_id = int(os.getenv('TELEGRAM_MONITORED_CHANNELS', '-1001827102719'))
        print(f"\nCurrent monitored channel ID: {current_channel_id}")
        
        # Get channel info
        try:
            channel = await client.get_entity(current_channel_id)
            print(f"Channel title: {channel.title}")
            print(f"Channel username: @{channel.username}" if hasattr(channel, 'username') and channel.username else "No username")
            print(f"Channel type: {type(channel).__name__}")
            
            # Channel info retrieved successfully
            
        except Exception as e:
            print(f"Error getting channel info: {e}")
            
        # Channel info retrieved successfully
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(get_channel_info())
