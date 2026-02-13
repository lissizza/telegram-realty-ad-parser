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

        # Create indexes for outgoing_posts collection
        # First, try to drop existing index if it exists (to handle migration)
        try:
            await db.outgoing_posts.drop_index("unique_ad_user_message")
            logger.info("Dropped existing unique_ad_user_message index")
        except Exception:
            pass  # Index doesn't exist, that's fine
        
        # Clean up problematic records with null values before creating index
        # These are old records that don't have proper references
        delete_result = await db.outgoing_posts.delete_many({
            "$or": [
                {"real_estate_ad_id": None},
                {"incoming_message_id": None}
            ]
        })
        if delete_result.deleted_count > 0:
            logger.info("Cleaned up %d outgoing_posts records with null values", delete_result.deleted_count)
        
        # Compound index for fast lookup: check if ad was already sent to user for specific incoming message
        # Use sparse=True to ignore documents where any indexed field is null
        # This allows the index to be created even if there are old records with null values
        try:
            await db.outgoing_posts.create_index([
                ("real_estate_ad_id", 1),
                ("sent_to", 1),
                ("incoming_message_id", 1)
            ], unique=True, sparse=True, name="unique_ad_user_message")
            logger.info("Created unique_ad_user_message index successfully")
        except Exception as e:
            logger.warning("Could not create unique_ad_user_message index (may already exist or have duplicates): %s", e)
            # Try to create non-unique index as fallback
            try:
                await db.outgoing_posts.create_index([
                    ("real_estate_ad_id", 1),
                    ("sent_to", 1),
                    ("incoming_message_id", 1)
                ], sparse=True, name="ad_user_message")
                logger.info("Created non-unique ad_user_message index as fallback")
            except Exception as e2:
                logger.error("Could not create fallback index: %s", e2)
        
        # Index for user queries
        await db.outgoing_posts.create_index("sent_to")
        # Index for ad queries (sparse to ignore null values)
        await db.outgoing_posts.create_index("real_estate_ad_id", sparse=True)
        # Index for incoming message queries (sparse to ignore null values)
        await db.outgoing_posts.create_index("incoming_message_id", sparse=True)
        # Index for time-based queries
        await db.outgoing_posts.create_index("sent_at")

        # Create indexes for channels collection
        await db.channels.create_index("is_monitored")
        await db.channels.create_index("is_real_estate_channel")

        logger.info("Database indexes created successfully")

    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
