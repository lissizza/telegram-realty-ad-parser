from datetime import datetime, UTC
from typing import List, Optional
import logging

from app.db.mongodb import mongodb
from app.models.price_filter import PriceFilter

logger = logging.getLogger(__name__)


class PriceFilterService:
    """Service for managing price filters"""
    
    async def create_price_filter(self, price_filter: PriceFilter) -> str:
        """Create a new price filter"""
        try:
            db = mongodb.get_database()
            
            # Convert to dict and add timestamps
            price_filter_dict = price_filter.model_dump()
            price_filter_dict["created_at"] = datetime.now(UTC)
            price_filter_dict["updated_at"] = datetime.now(UTC)
            
            result = await db.price_filters.insert_one(price_filter_dict)
            price_filter_id = str(result.inserted_id)
            
            logger.info("Created price filter %s for filter %s", price_filter_id, price_filter.filter_id)
            return price_filter_id
            
        except Exception as e:
            logger.error("Error creating price filter: %s", e)
            raise
    
    async def get_price_filters_by_filter_id(self, filter_id: str) -> List[PriceFilter]:
        """Get all price filters for a specific SimpleFilter"""
        try:
            db = mongodb.get_database()
            
            logger.info("Searching for price filters with filter_id: %s", filter_id)
            
            cursor = db.price_filters.find({
                "filter_id": filter_id,
                "is_active": True
            }).sort("created_at", 1)
            
            price_filters = []
            async for doc in cursor:
                logger.info("Found price filter: %s", doc)
                # Map MongoDB _id to API-facing id
                doc["id"] = str(doc.pop("_id"))
                # Ensure required fields are present
                if "is_active" not in doc:
                    doc["is_active"] = True
                try:
                    price_filter = PriceFilter(**doc)
                    price_filters.append(price_filter)
                except Exception as validation_error:
                    logger.error("Validation error for price filter: %s", validation_error)
                    logger.error("Document data: %s", doc)
                    raise
            
            logger.info("Found %d price filters for filter %s", len(price_filters), filter_id)
            return price_filters
            
        except Exception as e:
            logger.error("Error getting price filters for filter %s: %s", filter_id, e)
            return []
    
    async def update_price_filter(self, price_filter_id: str, update_data: dict) -> bool:
        """Update a price filter"""
        try:
            from bson import ObjectId
            db = mongodb.get_database()
            
            update_data["updated_at"] = datetime.now(UTC)
            
            result = await db.price_filters.update_one(
                {"_id": ObjectId(price_filter_id)},
                {"$set": update_data}
            )
            
            if result.matched_count > 0:
                logger.info("Updated price filter %s", price_filter_id)
                return True
            else:
                logger.warning("Price filter %s not found for update", price_filter_id)
                return False
                
        except Exception as e:
            logger.error("Error updating price filter %s: %s", price_filter_id, e)
            return False
    
    async def delete_price_filter(self, price_filter_id: str) -> bool:
        """Delete a price filter (soft delete by setting is_active=False)"""
        try:
            from bson import ObjectId
            db = mongodb.get_database()
            
            result = await db.price_filters.update_one(
                {"_id": ObjectId(price_filter_id)},
                {
                    "$set": {
                        "is_active": False,
                        "updated_at": datetime.now(UTC)
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info("Deleted price filter %s", price_filter_id)
                return True
            else:
                logger.warning("Price filter %s not found for deletion", price_filter_id)
                return False
                
        except Exception as e:
            logger.error("Error deleting price filter %s: %s", price_filter_id, e)
            return False
    
    async def delete_price_filters_by_filter_id(self, filter_id: str) -> int:
        """Delete all price filters for a specific SimpleFilter"""
        try:
            db = mongodb.get_database()
            
            result = await db.price_filters.update_many(
                {"filter_id": filter_id},
                {
                    "$set": {
                        "is_active": False,
                        "updated_at": datetime.now(UTC)
                    }
                }
            )
            
            logger.info("Deleted %d price filters for filter %s", result.modified_count, filter_id)
            return result.modified_count
            
        except Exception as e:
            logger.error("Error deleting price filters for filter %s: %s", filter_id, e)
            return 0
