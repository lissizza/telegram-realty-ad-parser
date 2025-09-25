#!/usr/bin/env python3
"""Test script to debug API endpoint"""

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
        logging.FileHandler('/app/api_test.log')
    ]
)

logger = logging.getLogger(__name__)

async def test_api_endpoint():
    """Test the API endpoint directly"""
    try:
        from app.api.v1.endpoints.user_channel_subscriptions import get_user_subscriptions
        from app.services.user_channel_subscription_service import UserChannelSubscriptionService
        from app.db.mongodb import mongodb
        
        logger.info("Starting API endpoint test")
        
        # Connect to MongoDB
        await mongodb.connect_to_mongo()
        logger.info("Connected to MongoDB")
        
        # Create service
        service = UserChannelSubscriptionService()
        logger.info("Created UserChannelSubscriptionService")
        
        # Test the API endpoint function directly
        logger.info("Testing get_user_subscriptions endpoint...")
        try:
            result = await get_user_subscriptions(user_id=None, active_only=False, service=service)
            logger.info("API endpoint returned %s subscriptions", len(result))
            for i, sub in enumerate(result):
                logger.info("API result %s: %s", i, sub)
        except Exception as api_error:
            logger.error("API endpoint error: %s", api_error, exc_info=True)
        
    except Exception as e:
        logger.error("Error in test: %s", e, exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_api_endpoint())

