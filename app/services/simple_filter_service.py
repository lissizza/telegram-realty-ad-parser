"""
Simple filter service for managing real estate filters.

This module provides functionality to create, update, delete, and check
simple filters against real estate advertisements.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.db.mongodb import mongodb
from app.models.simple_filter import SimpleFilter
from app.models.telegram import RealEstateAd

logger = logging.getLogger(__name__)


class SimpleFilterService:
    """Service for managing simple filters"""

    async def get_active_filters(self) -> List[SimpleFilter]:
        """Get all active simple filters"""
        try:
            db = mongodb.get_database()
            filters = []

            async for filter_doc in db.simple_filters.find({"is_active": True}):
                filter_doc["id"] = str(filter_doc["_id"])
                filters.append(SimpleFilter(**filter_doc))

            return filters
        except Exception as e:
            logger.error("Error getting active filters: %s", e)
            return []

    async def get_filter_by_id(self, filter_id: str) -> Optional[SimpleFilter]:
        """Get a specific simple filter by ID"""
        try:
            db = mongodb.get_database()
            object_id = ObjectId(filter_id)
            filter_doc = await db.simple_filters.find_one({"_id": object_id})

            if filter_doc:
                filter_doc["id"] = str(filter_doc["_id"])
                return SimpleFilter(**filter_doc)
            return None
        except Exception as e:
            logger.error("Error getting filter by ID: %s", e)
            return None

    async def check_filters(self, real_estate_ad: RealEstateAd) -> Dict[str, Any]:
        """Check if real estate ad matches any active filters"""
        try:
            filters = await self.get_active_filters()
            matching_filters = []
            filter_details = {}

            logger.info(
                "Checking %s filters for ad: property_type=%s, rooms=%s",
                len(filters),
                real_estate_ad.property_type,
                real_estate_ad.rooms_count,
            )

            for filter_obj in filters:
                logger.info(
                    "Checking filter '%s': property_types=%s, min_rooms=%s, max_rooms=%s",
                    filter_obj.name,
                    filter_obj.property_types,
                    filter_obj.min_rooms,
                    filter_obj.max_rooms,
                )
                if filter_obj.matches(real_estate_ad):
                    filter_id = str(filter_obj.id) if filter_obj.id else "unknown"
                    matching_filters.append(filter_id)
                    filter_details[filter_id] = {"name": filter_obj.name, "description": filter_obj.description}
                    logger.info("Filter '%s' MATCHED!", filter_obj.name)
                else:
                    logger.info("Filter '%s' did not match", filter_obj.name)

            return {
                "matching_filters": matching_filters,
                "filter_details": filter_details,
                "should_forward": len(matching_filters) > 0,
            }

        except Exception as e:
            logger.error("Error checking filters: %s", e)
            return {"matching_filters": [], "filter_details": {}, "should_forward": False}

    async def create_filter(self, filter_data: dict) -> str:
        """Create a new simple filter"""
        try:
            db = mongodb.get_database()
            filter_obj = SimpleFilter(**filter_data)

            result = await db.simple_filters.insert_one(filter_obj.dict())
            return str(result.inserted_id)

        except Exception as e:
            logger.error("Error creating filter: %s", e)
            raise

    async def update_filter(self, filter_id: str, filter_data: dict) -> bool:
        """Update an existing simple filter"""
        try:
            logger.info("Updating filter %s with data: %s", filter_id, filter_data)
            db = mongodb.get_database()

            # Add updated_at timestamp
            filter_data["updated_at"] = datetime.now(timezone.utc)
            logger.info("Filter data with timestamp: %s", filter_data)

            result = await db.simple_filters.update_one({"_id": ObjectId(filter_id)}, {"$set": filter_data})

            logger.info("Update result: modified_count=%s", result.modified_count)
            success = bool(result.modified_count > 0)
            logger.info("Update successful: %s", success)

            return success

        except Exception as e:
            logger.error("Error updating filter: %s", e, exc_info=True)
            raise

    async def delete_filter(self, filter_id: str) -> bool:
        """Delete a simple filter"""
        try:
            db = mongodb.get_database()

            result = await db.simple_filters.delete_one({"_id": ObjectId(filter_id)})
            return bool(result.deleted_count > 0)

        except Exception as e:
            logger.error("Error deleting filter: %s", e)
            raise

    async def get_filter_dict_by_id(self, filter_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific filter by ID as dictionary"""
        try:
            db = mongodb.get_database()
            filter_doc = await db.simple_filters.find_one({"_id": ObjectId(filter_id)})

            if not filter_doc:
                return None

            # Convert ObjectId to string for JSON serialization
            filter_doc["id"] = str(filter_doc["_id"])
            filter_doc["_id"] = str(filter_doc["_id"])

            return dict(filter_doc)

        except Exception as e:
            logger.error("Error getting filter by ID: %s", e)
            return None

    async def toggle_filter_status(self, filter_id: str) -> bool:
        """Toggle filter active status"""
        try:
            db = mongodb.get_database()

            # Get current status
            filter_doc = await db.simple_filters.find_one({"_id": ObjectId(filter_id)})
            if not filter_doc:
                return False

            new_status = not filter_doc.get("is_active", True)

            result = await db.simple_filters.update_one(
                {"_id": ObjectId(filter_id)},
                {"$set": {"is_active": new_status, "updated_at": datetime.now(timezone.utc)}},
            )

            return bool(result.modified_count > 0)

        except Exception as e:
            logger.error("Error toggling filter status: %s", e)
            raise
