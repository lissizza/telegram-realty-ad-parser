"""
Service for managing user filter matches
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId

from app.db.mongodb import mongodb
from app.models.user_filter_match import UserFilterMatch

logger = logging.getLogger(__name__)


class UserFilterMatchService:
    """Service for managing user filter matches"""

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
            logger.error("Error deleting matches for filter %s: %s", filter_id, e)
            return 0
