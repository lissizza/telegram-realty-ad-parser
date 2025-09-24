from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

from app.core.config import settings


class MongoDB:
    client: AsyncIOMotorClient = None
    sync_client: MongoClient = None

    async def connect_to_mongo(self):
        """Create database connection"""
        self.client = AsyncIOMotorClient(settings.MONGODB_URL)
        self.sync_client = MongoClient(settings.MONGODB_URL)
        print("Connected to MongoDB")

    async def close_mongo_connection(self):
        """Close database connection"""
        if self.client:
            self.client.close()
        if self.sync_client:
            self.sync_client.close()
        print("Disconnected from MongoDB")

    def get_database(self):
        """Get database instance"""
        return self.client.get_database()

    def get_sync_database(self):
        """Get synchronous database instance"""
        return self.sync_client.get_database()

    @staticmethod
    def get_current_time():
        """Get current UTC time"""
        return datetime.now(timezone.utc)


mongodb = MongoDB()
