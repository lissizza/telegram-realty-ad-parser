import logging
from datetime import datetime

from app.db.mongodb import mongodb
from app.models.telegram import PropertyType, RentalType

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

        # Create sample filter if none exist
        await create_sample_filter(db)

    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


async def create_sample_filter(db):
    """Create a sample filter if no filters exist"""
    try:
        filter_count = await db.simple_filters.count_documents({})

        if filter_count == 0:
            sample_filter = {
                "name": "Sample 2-3 Room Apartment Filter",
                "description": "Looking for 2-3 room apartments in any district",
                "property_types": [PropertyType.APARTMENT],
                "rental_types": [RentalType.LONG_TERM],
                "min_rooms": 2,
                "max_rooms": 3,
                "min_price": 100000,
                "max_price": 500000,
                "price_currency": "AMD",
                "districts": ["Центр", "Кентрон", "Арабкир"],
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            await db.simple_filters.insert_one(sample_filter)
            logger.info("Sample filter created")

    except Exception as e:
        logger.error(f"Error creating sample filter: {e}")
