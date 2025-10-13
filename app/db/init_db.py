import logging

from app.db.mongodb import mongodb

logger = logging.getLogger(__name__)


async def init_database():
    """Initialize database with collections and indexes"""
    try:
        db = mongodb.get_database()

        # Create indexes for posts collection
        await db.incoming_messages.create_index("channel_id")
        await db.incoming_messages.create_index("date")
        await db.incoming_messages.create_index([("channel_id", 1), ("date", -1)])

        # Create indexes for real_estate_ads collection
        await db.real_estate_ads.create_index("original_post_id", unique=True)
        await db.real_estate_ads.create_index("property_type")
        await db.real_estate_ads.create_index("price")
        await db.real_estate_ads.create_index("district")
        await db.real_estate_ads.create_index("created_at")
        await db.real_estate_ads.create_index([("property_type", 1), ("price", 1)])

        # Create indexes for simple_filters collection
        await db.simple_filters.create_index("is_active")
        await db.simple_filters.create_index("created_at")

        # Create indexes for forwarded_posts collection
        await db.forwarded_posts.create_index("original_post_id")
        await db.forwarded_posts.create_index("filter_id")
        await db.forwarded_posts.create_index("forwarded_at")

        # Create indexes for channels collection
        await db.channels.create_index("is_monitored")
        await db.channels.create_index("is_real_estate_channel")

        logger.info("Database indexes created successfully")

    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
