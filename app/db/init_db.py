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
        await db.incoming_messages.create_index([("id", 1), ("channel_id", 1)])

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
        await db.simple_filters.create_index([("is_active", 1), ("user_id", 1)])

        # Create indexes for price_filters collection
        await db.price_filters.create_index([("filter_id", 1), ("is_active", 1)])

        # Create indexes for user_channel_selections collection
        await db.user_channel_selections.create_index([("user_id", 1), ("channel_id", 1)])

        # Create indexes for user_filter_matches collection
        await db.user_filter_matches.create_index([("user_id", 1), ("filter_id", 1)])

        # Create indexes for forwarded_posts collection
        await db.forwarded_posts.create_index("original_post_id")
        await db.forwarded_posts.create_index("filter_id")
        await db.forwarded_posts.create_index("forwarded_at")

        # Create indexes for outgoing_posts collection
        # Compound index for fast lookup: check if ad was already sent to user for specific incoming message
        # Use sparse=True to ignore documents where any indexed field is null
        try:
            await db.outgoing_posts.create_index([
                ("real_estate_ad_id", 1),
                ("sent_to", 1),
                ("incoming_message_id", 1)
            ], unique=True, sparse=True, name="unique_ad_user_message")
        except Exception as e:
            logger.warning("Could not create unique_ad_user_message index (may already exist): %s", e)
            # Try to create non-unique index as fallback
            try:
                await db.outgoing_posts.create_index([
                    ("real_estate_ad_id", 1),
                    ("sent_to", 1),
                    ("incoming_message_id", 1)
                ], sparse=True, name="ad_user_message")
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
        logger.error("Error initializing database: %s", e)
        raise
