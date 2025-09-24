"""
Pytest configuration and fixtures for testing
"""

import asyncio

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.db.mongodb import mongodb


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_database():
    """Create a test database for each test function"""
    # Use a test database
    test_db_name = "test_rent_bot"

    # Create test client
    test_client = AsyncIOMotorClient(settings.MONGODB_URL)
    test_db = test_client[test_db_name]

    # Store original client
    original_client = mongodb.client

    # Set test client
    mongodb.client = test_client

    # Clean up collections before test
    collections = await test_db.list_collection_names()
    for collection_name in collections:
        await test_db.drop_collection(collection_name)

    yield test_db

    # Cleanup: drop test database
    await test_client.drop_database(test_db_name)
    await test_client.close()

    # Restore original client
    mongodb.client = original_client
