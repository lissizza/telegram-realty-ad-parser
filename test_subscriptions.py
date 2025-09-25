#!/usr/bin/env python3
"""Test script to debug subscription service"""

import asyncio
import logging
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, '/app')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/test.log')
    ]
)

logger = logging.getLogger(__name__)

async def test_subscription_service():
    """Test the subscription service directly"""
    try:
        from app.services.user_channel_subscription_service import UserChannelSubscriptionService
        from app.db.mongodb import mongodb
        
        logger.info("Starting subscription service test")
        
        # Connect to MongoDB
        await mongodb.connect_to_mongo()
        logger.info("Connected to MongoDB")
        
        # Create service
        service = UserChannelSubscriptionService()
        logger.info("Created UserChannelSubscriptionService")
        
        # Test get_all_active_subscriptions
        logger.info("Testing get_all_active_subscriptions...")
        subscriptions = await service.get_all_active_subscriptions()
        logger.info("Found %s subscriptions", len(subscriptions))
        
        for i, sub in enumerate(subscriptions):
            logger.info("Subscription %s: %s", i, sub)
        
        # Test debug endpoint logic
        logger.info("Testing debug endpoint logic...")
        db = mongodb.get_database()
        if db is not None:
            all_subscriptions = []
            async for sub in db.user_channel_subscriptions.find():
                logger.info("Raw doc from DB: %s", sub)
                all_subscriptions.append({
                    "id": str(sub["_id"]),
                    "user_id": sub["user_id"],
                    "channel_username": sub.get("channel_username"),
                    "is_active": sub.get("is_active", True)
                })
            
            logger.info("Found %s raw subscriptions", len(all_subscriptions))
            for sub in all_subscriptions:
                logger.info("Processed subscription: %s", sub)
        
    except Exception as e:
        logger.error("Error in test: %s", e, exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_subscription_service())
