import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from bson import ObjectId

from app.models.simple_filter import SimpleFilter
from app.models.telegram import RealEstateAd
from app.db.mongodb import mongodb

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
            logger.error(f"Error getting active filters: {e}")
            return []
    
    async def get_filter_by_id(self, filter_id: str) -> Optional[SimpleFilter]:
        """Get a specific simple filter by ID"""
        try:
            from bson import ObjectId
            db = mongodb.get_database()
            object_id = ObjectId(filter_id)
            filter_doc = await db.simple_filters.find_one({"_id": object_id})
            
            if filter_doc:
                filter_doc["id"] = str(filter_doc["_id"])
                return SimpleFilter(**filter_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting filter by ID: {e}")
            return None
    
    async def check_filters(self, real_estate_ad: RealEstateAd) -> Dict[str, Any]:
        """Check if real estate ad matches any active filters"""
        try:
            filters = await self.get_active_filters()
            matching_filters = []
            filter_details = {}
            
            logger.info(f"Checking {len(filters)} filters for ad: property_type={real_estate_ad.property_type}, rooms={real_estate_ad.rooms_count}")
            
            for filter_obj in filters:
                logger.info(f"Checking filter '{filter_obj.name}': property_types={filter_obj.property_types}, min_rooms={filter_obj.min_rooms}, max_rooms={filter_obj.max_rooms}")
                if filter_obj.matches(real_estate_ad):
                    filter_id = str(filter_obj.id) if filter_obj.id else "unknown"
                    matching_filters.append(filter_id)
                    filter_details[filter_id] = {
                        "name": filter_obj.name,
                        "description": filter_obj.description
                    }
                    logger.info(f"Filter '{filter_obj.name}' MATCHED!")
                else:
                    logger.info(f"Filter '{filter_obj.name}' did not match")
            
            return {
                "matching_filters": matching_filters,
                "filter_details": filter_details,
                "should_forward": len(matching_filters) > 0
            }
            
        except Exception as e:
            logger.error(f"Error checking filters: {e}")
            return {
                "matching_filters": [],
                "filter_details": {},
                "should_forward": False
            }
    
    async def create_filter(self, filter_data: dict) -> str:
        """Create a new simple filter"""
        try:
            db = mongodb.get_database()
            filter_obj = SimpleFilter(**filter_data)
            
            result = await db.simple_filters.insert_one(filter_obj.dict())
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creating filter: {e}")
            raise
    
    async def update_filter(self, filter_id: str, filter_data: dict) -> bool:
        """Update an existing simple filter"""
        try:
            logger.info(f"Updating filter {filter_id} with data: {filter_data}")
            db = mongodb.get_database()

            # Add updated_at timestamp
            filter_data["updated_at"] = datetime.utcnow()
            logger.info(f"Filter data with timestamp: {filter_data}")

            result = await db.simple_filters.update_one(
                {"_id": ObjectId(filter_id)},
                {"$set": filter_data}
            )

            logger.info(f"Update result: modified_count={result.modified_count}")
            success = result.modified_count > 0
            logger.info(f"Update successful: {success}")

            return success

        except Exception as e:
            logger.error(f"Error updating filter: {e}", exc_info=True)
            raise
    
    async def delete_filter(self, filter_id: str) -> bool:
        """Delete a simple filter"""
        try:
            db = mongodb.get_database()
            
            result = await db.simple_filters.delete_one({"_id": ObjectId(filter_id)})
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"Error deleting filter: {e}")
            raise
    
    async def get_filter_by_id(self, filter_id: str) -> dict:
        """Get a specific filter by ID"""
        try:
            db = mongodb.get_database()
            filter_doc = await db.simple_filters.find_one({"_id": ObjectId(filter_id)})

            if not filter_doc:
                return None

            # Convert ObjectId to string for JSON serialization
            filter_doc["id"] = str(filter_doc["_id"])
            filter_doc["_id"] = str(filter_doc["_id"])

            return filter_doc

        except Exception as e:
            logger.error(f"Error getting filter by ID: {e}")
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
                {"$set": {
                    "is_active": new_status,
                    "updated_at": datetime.utcnow()
                }}
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error toggling filter status: {e}")
            raise
