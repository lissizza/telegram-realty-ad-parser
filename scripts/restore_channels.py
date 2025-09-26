#!/usr/bin/env python3
"""
Script to restore channels and subscriptions after data loss
"""

import asyncio
import httpx
import json
from typing import Dict, Any

API_BASE = "http://localhost:8001/api/v1"

async def restore_channels_and_subscriptions():
    """Restore channels and user subscriptions"""
    
    # Channels to restore
    channels = [
        {
            "title": "АРЕНДА ЕРЕВАН | Недвижимость Армении",
            "username": "arenda_erevanNO1",
            "telegram_id": -1001843374707,
            "is_monitored": True,
            "is_real_estate_channel": True
        }
    ]
    
    # User subscriptions
    subscriptions = [
        {
            "user_id": 223720761,
            "channel_input": "arenda_erevanNO1",
            "is_active": True
        },
        {
            "user_id": 7497167557,
            "channel_input": "arenda_erevanNO1", 
            "is_active": True
        }
    ]
    
    async with httpx.AsyncClient() as client:
        # Create channels
        print("🔄 Creating channels...")
        channel_ids = {}
        
        for channel_data in channels:
            try:
                response = await client.post(
                    f"{API_BASE}/channels/",
                    json=channel_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    channel_ids[channel_data["username"]] = result["id"]
                    print(f"  ✅ Created channel: {channel_data['title']} (ID: {result['id']})")
                else:
                    print(f"  ❌ Failed to create channel {channel_data['title']}: {response.text}")
                    
            except Exception as e:
                print(f"  ❌ Error creating channel {channel_data['title']}: {e}")
        
        # Create subscriptions
        print("🔄 Creating user subscriptions...")
        
        for sub_data in subscriptions:
            try:
                response = await client.post(
                    f"{API_BASE}/user-channel-subscriptions/",
                    json=sub_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"  ✅ Created subscription for user {sub_data['user_id']} (ID: {result['subscription_id']})")
                else:
                    print(f"  ❌ Failed to create subscription for user {sub_data['user_id']}: {response.text}")
                    
            except Exception as e:
                print(f"  ❌ Error creating subscription for user {sub_data['user_id']}: {e}")
    
    print("✅ Channel and subscription restoration completed!")

if __name__ == "__main__":
    asyncio.run(restore_channels_and_subscriptions())
