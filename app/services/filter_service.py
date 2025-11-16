"""
Unified filter service for managing real estate filters and matches.

This module provides functionality to create, update, delete, and check
simple filters against real estate advertisements, as well as track
matches between users, filters, and ads.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.db.mongodb import mongodb
from app.models.simple_filter import SimpleFilter
from app.models.telegram import RealEstateAd
from app.models.price_filter import PriceFilter
from app.models.user_filter_match import UserFilterMatch
from app.services.price_filter_service import PriceFilterService

logger = logging.getLogger(__name__)


class FilterService:
    """Unified service for managing filters and matches"""
    
    def __init__(self):
        self.price_filter_service = PriceFilterService()

    # ==================== FILTER MANAGEMENT ====================

    async def get_active_filters(self, user_id: Optional[int] = None) -> List[SimpleFilter]:
        """Get all active simple filters, optionally filtered by user"""
        try:
            db = mongodb.get_database()
            filters = []

            query = {"is_active": True}
            if user_id is not None:
                query["user_id"] = user_id

            async for filter_doc in db.simple_filters.find(query):
                # Skip filters without user_id (legacy data)
                if "user_id" not in filter_doc:
                    logger.warning("Skipping filter %s without user_id", filter_doc.get("_id"))
                    continue
                    
                filter_doc["id"] = str(filter_doc["_id"])
                filters.append(SimpleFilter(**filter_doc))

            return filters
        except Exception as e:
            logger.error("Error getting active filters: %s", e)
            return []

    async def get_filter_by_id(self, filter_id: str) -> Optional[SimpleFilter]:
        """Get a specific filter by ID"""
        try:
            db = mongodb.get_database()
            filter_doc = await db.simple_filters.find_one({"_id": ObjectId(filter_id)})
            
            if filter_doc:
                filter_doc["id"] = str(filter_doc["_id"])
                return SimpleFilter(**filter_doc)
            return None
        except Exception as e:
            logger.error("Error getting filter %s: %s", filter_id, e)
            return None

    async def create_filter(self, filter_data: Dict[str, Any]) -> Optional[str]:
        """Create a new simple filter"""
        try:
            db = mongodb.get_database()
            
            # Add timestamps
            filter_data["created_at"] = datetime.now(timezone.utc)
            filter_data["updated_at"] = datetime.now(timezone.utc)
            
            result = await db.simple_filters.insert_one(filter_data)
            logger.info("Created new filter: %s", str(result.inserted_id))
            return str(result.inserted_id)
        except Exception as e:
            logger.error("Error creating filter: %s", e)
            return None

    async def update_filter(self, filter_id: str, update_data: Dict[str, Any]) -> bool:
        """Update an existing filter"""
        try:
            db = mongodb.get_database()
            
            # Add update timestamp
            update_data["updated_at"] = datetime.now(timezone.utc)
            
            result = await db.simple_filters.update_one(
                {"_id": ObjectId(filter_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info("Updated filter: %s", filter_id)
                return True
            return False
        except Exception as e:
            logger.error("Error updating filter %s: %s", filter_id, e)
            return False

    async def delete_filter(self, filter_id: str) -> bool:
        """Delete a filter and all its matches"""
        try:
            db = mongodb.get_database()
            
            # Delete all matches for this filter first
            await self.delete_matches_for_filter(filter_id)
            
            # Delete the filter
            result = await db.simple_filters.delete_one({"_id": ObjectId(filter_id)})
            
            if result.deleted_count > 0:
                logger.info("Deleted filter: %s", filter_id)
                return True
            return False
        except Exception as e:
            logger.error("Error deleting filter %s: %s", filter_id, e)
            return False

    # ==================== FILTER CHECKING ====================

    async def check_filters(self, real_estate_ad: RealEstateAd, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Check if real estate ad matches any active filters for a specific user"""
        try:
            filters = await self.get_active_filters(user_id)
            matching_filters = []
            filter_details = {}
            created_matches = []

            logger.info(
                "Checking %s filters for ad: property_type=%s, rooms=%s, user_id=%s",
                len(filters),
                real_estate_ad.property_type,
                real_estate_ad.rooms_count,
                user_id,
            )
            
            for filter_obj in filters:
                logger.info(
                    "Checking filter '%s': property_types=%s, min_rooms=%s, max_rooms=%s",
                    filter_obj.name,
                    filter_obj.property_types,
                    filter_obj.min_rooms,
                    filter_obj.max_rooms,
                )
                
                # Get price filters for this filter
                price_filters = []
                if filter_obj.id:
                    price_filters = await self.price_filter_service.get_price_filters_by_filter_id(str(filter_obj.id))
                
                # Check if filter matches (including price filters)
                logger.info("Filter '%s' has %d price filters: %s", filter_obj.name, len(price_filters),
                           [(pf.min_price, pf.max_price, pf.currency) for pf in price_filters] if price_filters else [])
                logger.info("Ad price: %s %s", real_estate_ad.price, real_estate_ad.currency)
                # Always use matches_with_price_filters method (handles both cases: with and without price filters)
                matches = filter_obj.matches_with_price_filters(real_estate_ad, price_filters)
                logger.info("Filter '%s' matches after price check: %s", filter_obj.name, matches)
                
                if matches:
                    filter_id = str(filter_obj.id) if filter_obj.id else "unknown"
                    matching_filters.append(filter_id)
                    filter_details[filter_id] = {"name": filter_obj.name, "description": filter_obj.description}
                    logger.info("Filter '%s' MATCHED!", filter_obj.name)
                    
                    # Create user filter match record
                    if user_id and real_estate_ad.id:
                        match_id = await self.create_match(
                            user_id=user_id,
                            filter_id=filter_id,
                            real_estate_ad_id=real_estate_ad.id
                        )
                        if match_id:
                            created_matches.append(match_id)
                else:
                    logger.info("Filter '%s' did not match", filter_obj.name)

            return {
                "matching_filters": matching_filters,
                "filter_details": filter_details,
                "created_matches": created_matches,
                "total_checked": len(filters)
            }
        except Exception as e:
            logger.error("Error checking filters: %s", e)
            return {
                "matching_filters": [],
                "filter_details": {},
                "created_matches": [],
                "total_checked": 0,
                "error": str(e)
            }

    # ==================== MATCH MANAGEMENT ====================

    async def create_match(
        self, user_id: int, filter_id: str, real_estate_ad_id: str
    ) -> Optional[str]:
        """Create a new user filter match"""
        try:
            db = mongodb.get_database()
            
            # Check if match already exists
            existing_match = await db.user_filter_matches.find_one({
                "user_id": user_id,
                "filter_id": filter_id,
                "real_estate_ad_id": real_estate_ad_id
            })
            
            if existing_match:
                logger.info("Match already exists for user %s, filter %s, ad %s",
                           user_id, filter_id, real_estate_ad_id)
                return str(existing_match["_id"])
            
            # Create new match
            match = UserFilterMatch(
                user_id=user_id,
                filter_id=filter_id,
                real_estate_ad_id=real_estate_ad_id
            )
            
            result = await db.user_filter_matches.insert_one(match.model_dump())
            logger.info("Created user filter match: %s", str(result.inserted_id))
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error("Error creating user filter match: %s", e)
            return None

    async def get_matches_for_user(self, user_id: int, limit: int = 100) -> List[UserFilterMatch]:
        """Get all matches for a specific user"""
        try:
            db = mongodb.get_database()
            matches = []
            
            async for match_doc in db.user_filter_matches.find(
                {"user_id": user_id}
            ).sort("matched_at", -1).limit(limit):
                match_doc["id"] = str(match_doc["_id"])
                matches.append(UserFilterMatch(**match_doc))
            
            return matches
        except Exception as e:
            logger.error("Error getting matches for user %s: %s", user_id, e)
            return []

    async def get_matches_for_ad(self, real_estate_ad_id: str) -> List[UserFilterMatch]:
        """Get all matches for a specific real estate ad"""
        try:
            db = mongodb.get_database()
            matches = []
            
            async for match_doc in db.user_filter_matches.find(
                {"real_estate_ad_id": real_estate_ad_id}
            ):
                match_doc["id"] = str(match_doc["_id"])
                matches.append(UserFilterMatch(**match_doc))
            
            return matches
        except Exception as e:
            logger.error("Error getting matches for ad %s: %s", real_estate_ad_id, e)
            return []

    async def mark_as_forwarded(self, match_id: str) -> bool:
        """Mark a match as forwarded"""
        try:
            db = mongodb.get_database()
            
            result = await db.user_filter_matches.update_one(
                {"_id": ObjectId(match_id)},
                {
                    "$set": {
                        "forwarded": True,
                        "forwarded_at": datetime.now(timezone.utc),
                        "status": "forwarded",
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            return bool(result.modified_count > 0)
        except Exception as e:
            logger.error("Error marking match as forwarded: %s", e)
            return False

    async def get_unforwarded_matches_for_user(self, user_id: int) -> List[UserFilterMatch]:
        """Get all unforwarded matches for a user"""
        try:
            db = mongodb.get_database()
            matches = []
            
            async for match_doc in db.user_filter_matches.find({
                "user_id": user_id,
                "forwarded": False
            }).sort("matched_at", -1):
                match_doc["id"] = str(match_doc["_id"])
                matches.append(UserFilterMatch(**match_doc))
            
            return matches
        except Exception as e:
            logger.error("Error getting unforwarded matches for user %s: %s", user_id, e)
            return []

    async def delete_matches_for_filter(self, filter_id: str) -> int:
        """Delete all matches for a specific filter"""
        try:
            db = mongodb.get_database()
            
            result = await db.user_filter_matches.delete_many({"filter_id": filter_id})
            logger.info("Deleted %s matches for filter %s", result.deleted_count, filter_id)
            return result.deleted_count
        except Exception as e:
            logger.error("Error deleting matches for filter %s: %s", e)
            return 0

    # ==================== STATISTICS ====================

    async def get_filter_stats(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get statistics about filters and matches"""
        try:
            db = mongodb.get_database()
            
            # Count active filters
            filter_query = {"is_active": True}
            if user_id is not None:
                filter_query["user_id"] = user_id
            
            total_filters = await db.simple_filters.count_documents(filter_query)
            
            # Count total matches
            match_query = {}
            if user_id is not None:
                match_query["user_id"] = user_id
            
            total_matches = await db.user_filter_matches.count_documents(match_query)
            forwarded_matches = await db.user_filter_matches.count_documents({**match_query, "forwarded": True})
            
            return {
                "total_filters": total_filters,
                "total_matches": total_matches,
                "forwarded_matches": forwarded_matches,
                "unforwarded_matches": total_matches - forwarded_matches
            }
        except Exception as e:
            logger.error("Error getting filter stats: %s", e)
            return {
                "total_filters": 0,
                "total_matches": 0,
                "forwarded_matches": 0,
                "unforwarded_matches": 0
            }


