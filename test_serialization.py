#!/usr/bin/env python3
"""Test script to debug serialization"""

import asyncio
import logging
import sys
import os
import json

# Add the app directory to Python path
sys.path.insert(0, '/app')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/serialization_test.log')
    ]
)

logger = logging.getLogger(__name__)

async def test_serialization():
    """Test serialization of subscription responses"""
    try:
        from app.services.user_channel_subscription_service import UserChannelSubscriptionService
        from app.db.mongodb import mongodb
        from app.models.user_channel_subscription import UserChannelSubscriptionResponse
        
        logger.info("Starting serialization test")
        
        # Connect to MongoDB
        await mongodb.connect_to_mongo()
        logger.info("Connected to MongoDB")
        
        # Create service
        service = UserChannelSubscriptionService()
        logger.info("Created UserChannelSubscriptionService")
        
        # Get subscriptions
        subscriptions = await service.get_all_active_subscriptions()
        logger.info("Found %s subscriptions", len(subscriptions))
        
        # Test serialization
        for i, sub in enumerate(subscriptions):
            logger.info("Testing subscription %s:", i)
            logger.info("  Type: %s", type(sub))
            logger.info("  Object: %s", sub)
            
            try:
                # Test JSON serialization
                json_str = json.dumps(sub.dict(), default=str)
                logger.info("  JSON serialization successful: %s", json_str[:100] + "..." if len(json_str) > 100 else json_str)
            except Exception as json_error:
                logger.error("  JSON serialization failed: %s", json_error)
            
            try:
                # Test model validation
                validated = UserChannelSubscriptionResponse(**sub.dict())
                logger.info("  Model validation successful")
            except Exception as validation_error:
                logger.error("  Model validation failed: %s", validation_error)
        
    except Exception as e:
        logger.error("Error in test: %s", e, exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_serialization())

