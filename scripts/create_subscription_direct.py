#!/usr/bin/env python3
"""
Script to create user channel subscriptions directly in database
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, UTC

# Database connection
MONGODB_URL = "mongodb://mongo:27017"
DATABASE_NAME = "telegram_bot"

async def create_subscriptions():
    """Create user channel subscriptions directly in database"""
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    
    # Subscriptions to create
    subscriptions = [
        {
            "user_id": 223720761,
            "channel_id": "68d6beab06991bca1f026715",  # ID канала из базы
            "channel_title": "АРЕНДА ЕРЕВАН | Недвижимость Армении",
            "channel_username": "arenda_erevanNO1",
            "channel_link": "https://t.me/arenda_erevanNO1",
            "topic_id": None,
            "topic_title": None,
            "is_active": True,
            "monitor_all_topics": True,
            "monitored_topics": [],
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC)
        },
        {
            "user_id": 7497167557,
            "channel_id": "68d6beab06991bca1f026715",  # ID канала из базы
            "channel_title": "АРЕНДА ЕРЕВАН | Недвижимость Армении",
            "channel_username": "arenda_erevanNO1",
            "channel_link": "https://t.me/arenda_erevanNO1",
            "topic_id": None,
            "topic_title": None,
            "is_active": True,
            "monitor_all_topics": True,
            "monitored_topics": [],
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC)
        }
    ]
    
    try:
        for subscription in subscriptions:
            # Check if subscription already exists
            existing = await db.user_channel_subscriptions.find_one({
                "user_id": subscription["user_id"],
                "channel_id": subscription["channel_id"]
            })
            
            if existing:
                print(f"⚠️  Подписка для пользователя {subscription['user_id']} уже существует")
                continue
            
            # Create subscription
            result = await db.user_channel_subscriptions.insert_one(subscription)
            print(f"✅ Создана подписка для пользователя {subscription['user_id']} (ID: {result.inserted_id})")
        
        print("✅ Все подписки созданы!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(create_subscriptions())
