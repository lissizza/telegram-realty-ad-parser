#!/usr/bin/env python3
"""
Script to get subchannel ID for "Сдача жилья без комиссии"
"""
import asyncio
import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from core.config import settings
from services.telegram_service import TelegramService

async def get_subchannel_id():
    """Get subchannel ID"""
    
    print(f"Current monitored channel: {settings.TELEGRAM_MONITORED_CHANNELS}")
    
    # Create telegram service
    service = TelegramService()
    
    try:
        # Initialize client
        from telethon import TelegramClient
        client = TelegramClient(
            settings.TELEGRAM_SESSION_NAME,
            settings.TELEGRAM_API_ID,
            settings.TELEGRAM_API_HASH
        )
        
        await client.start(phone=settings.TELEGRAM_PHONE)
        print("Connected to Telegram!")
        
        # Get current channel info
        current_channel_id = int(settings.TELEGRAM_MONITORED_CHANNELS)
        channel = await client.get_entity(current_channel_id)
        print(f"Current channel: {channel.title}")
        print(f"Channel type: {type(channel).__name__}")
        
        # Search for subchannels with specific keywords
        print("\nSearching for subchannels...")
        found_channels = []
        
        async for dialog in client.iter_dialogs():
            if hasattr(dialog.entity, 'title'):
                title = dialog.entity.title
                title_lower = title.lower()
                
                # Look for channels with "сдача" and "комиссия"
                if 'сдача' in title_lower and 'комиссия' in title_lower:
                    found_channels.append({
                        'title': title,
                        'id': dialog.entity.id,
                        'type': type(dialog.entity).__name__,
                        'username': getattr(dialog.entity, 'username', None)
                    })
                    print(f"Found: {title} (ID: {dialog.entity.id})")
        
        if found_channels:
            print(f"\nFound {len(found_channels)} matching channels:")
            for i, ch in enumerate(found_channels, 1):
                print(f"{i}. {ch['title']}")
                print(f"   ID: {ch['id']}")
                print(f"   Type: {ch['type']}")
                if ch['username']:
                    print(f"   Username: @{ch['username']}")
                print()
        else:
            print("No matching channels found.")
            print("\nAll channels with 'сдача' in title:")
            async for dialog in client.iter_dialogs():
                if hasattr(dialog.entity, 'title') and 'сдача' in dialog.entity.title.lower():
                    print(f"- {dialog.entity.title} (ID: {dialog.entity.id})")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await client.disconnect()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(get_subchannel_id())



