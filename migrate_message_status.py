#!/usr/bin/env python3
"""
Migration script to update existing posts with new status fields
"""
import asyncio
import logging
from datetime import datetime

from app.db.mongodb import mongodb
from app.models.message_status import MessageStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_posts():
    """Migrate existing posts to include status fields"""
    try:
        # Initialize MongoDB connection
        await mongodb.connect_to_mongo()
        db = mongodb.get_database()
        
        # Get all posts without status field
        posts_without_status = await db.posts.find({"status": {"$exists": False}}).to_list(length=None)
        
        logger.info(f"Found {len(posts_without_status)} posts without status field")
        
        for post in posts_without_status:
            # Determine status based on existing fields
            status = MessageStatus.RECEIVED
            
            if post.get("is_spam"):
                status = MessageStatus.SPAM_FILTERED
            elif post.get("is_real_estate") is False:
                status = MessageStatus.NOT_REAL_ESTATE
            elif post.get("is_real_estate") is True:
                if post.get("forwarded"):
                    status = MessageStatus.FORWARDED
                else:
                    status = MessageStatus.PARSED
            
            # Update the post
            update_data = {
                "status": status,
                "parsing_errors": [],
                "updated_at": datetime.utcnow()
            }
            
            # Add missing fields if they don't exist
            if "is_spam" not in post:
                update_data["is_spam"] = None
            if "spam_reason" not in post:
                update_data["spam_reason"] = None
            if "is_real_estate" not in post:
                update_data["is_real_estate"] = None
            if "real_estate_confidence" not in post:
                update_data["real_estate_confidence"] = None
            if "forwarded" not in post:
                update_data["forwarded"] = False
            if "forwarded_at" not in post:
                update_data["forwarded_at"] = None
            if "forwarded_to" not in post:
                update_data["forwarded_to"] = None
            
            await db.posts.update_one(
                {"_id": post["_id"]},
                {"$set": update_data}
            )
            
            logger.info(f"Updated post {post['id']} with status {status}")
        
        logger.info("Migration completed successfully")
        
        # Show statistics after migration
        status_pipeline = [
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        status_breakdown = await db.posts.aggregate(status_pipeline).to_list(length=None)
        logger.info("Status breakdown after migration:")
        for item in status_breakdown:
            logger.info(f"  {item['_id']}: {item['count']}")
            
        # Close MongoDB connection
        await mongodb.close_mongo_connection()
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


async def main():
    """Main migration function"""
    try:
        await migrate_posts()
    except Exception as e:
        logger.error(f"Migration script failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
