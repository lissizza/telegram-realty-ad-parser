import logging
from datetime import datetime, UTC
from typing import List, Optional, Union

from bson import ObjectId

from app.core.config import settings
from app.db.mongodb import mongodb
from app.models.user_channel_selection import (
    UserChannelSelectionCreate,
    UserChannelSelectionResponse,
    UserChannelSelectionBulkUpdate,
)
from app.services.monitored_channel_service import MonitoredChannelService
from app.utils.channel_id_utils import normalize_channel_id, channel_id_to_string

logger = logging.getLogger(__name__)


class UserChannelSelectionService:
    """Service for managing user channel selections"""

    def __init__(self):
        self.monitored_channel_service = MonitoredChannelService()

    async def _get_db(self):
        """Get database instance"""
        # Ensure MongoDB is connected
        if mongodb.client is None:
            await mongodb.connect_to_mongo()
        
        db = mongodb.get_database()
        if db is None:
            raise Exception("Database not initialized. Make sure MongoDB is connected.")
        return db

    async def get_user_selected_channels(self, user_id: int) -> List[UserChannelSelectionResponse]:
        """Get user's selected channels"""
        try:
            db = await self._get_db()
            selections = []
            async for doc in db.user_channel_selections.find({"user_id": user_id}):
                selections.append(UserChannelSelectionResponse.from_db_doc(doc))
            
            return selections
            
        except Exception as e:
            logger.error("Error getting user selected channels: %s", e)
            return []

    async def get_user_selected_channel_ids(self, user_id: int) -> List[str]:
        """Get list of selected channel IDs for a user"""
        try:
            db = await self._get_db()
            channel_ids = []
            async for doc in db.user_channel_selections.find({
                "user_id": user_id,
                "is_selected": True
            }):
                channel_ids.append(doc["channel_id"])
            
            return channel_ids
            
        except Exception as e:
            logger.error("Error getting user selected channel IDs: %s", e)
            return []

    async def get_available_channels_for_user(self, user_id: int) -> tuple[List[dict], bool]:
        """Get all monitored channels with user's selection status"""
        try:
            # Get all active monitored channels
            monitored_channels = await self.monitored_channel_service.get_active_channels()

            # Get user's current selections
            user_selections = await self.get_user_selected_channels(user_id)
            user_selection_map = {sel.channel_id: sel.is_selected for sel in user_selections}

            # Check if user has any selected channels
            has_any_selected = any(sel.is_selected for sel in user_selections)

            # If user has no selections at all OR no channels are selected, select all channels by default
            auto_selected = False
            if not user_selections or not has_any_selected:
                logger.info("User %s has no selections or no channels selected, selecting all channels by default", user_id)
                # Auto-select all channels for new users or users with no selections
                all_channel_ids = [channel.id for channel in monitored_channels]
                if all_channel_ids:
                    from app.models.user_channel_selection import UserChannelSelectionBulkUpdate
                    update_data = UserChannelSelectionBulkUpdate(
                        user_id=user_id,
                        selected_channel_ids=all_channel_ids
                    )
                    await self.update_user_channel_selections(update_data)
                    # Update selection map
                    user_selection_map = {channel_id: True for channel_id in all_channel_ids}
                    auto_selected = True

            # Combine data
            available_channels = []
            for channel in monitored_channels:
                available_channels.append({
                    "id": channel.id,
                    "channel_id": channel.channel_id,
                    "channel_username": channel.channel_username,
                    "channel_title": channel.channel_title,
                    "channel_link": channel.channel_link,
                    "topic_id": channel.topic_id,
                    "topic_title": channel.topic_title,
                    "is_selected": user_selection_map.get(channel.id, False),  # Default to False
                    "is_active": channel.is_active
                })

            return available_channels, auto_selected

        except Exception as e:
            logger.error("Error getting available channels for user: %s", e)
            return [], False

    async def update_user_channel_selections(self, update_data: UserChannelSelectionBulkUpdate) -> bool:
        """Update user's channel selections (bulk update)"""
        try:
            db = await self._get_db()
            user_id = update_data.user_id
            selected_channel_ids = set(update_data.selected_channel_ids)
            
            # Get all monitored channels to validate
            monitored_channels = await self.monitored_channel_service.get_active_channels()
            valid_channel_ids = {channel.id for channel in monitored_channels}
            
            # Validate that all selected channels are valid
            invalid_channels = selected_channel_ids - valid_channel_ids
            if invalid_channels:
                logger.warning("Invalid channel IDs provided: %s", invalid_channels)
                # Remove invalid channels from selection
                selected_channel_ids = selected_channel_ids - invalid_channels
            
            # Get current selections
            current_selections = await self.get_user_selected_channels(user_id)
            current_channel_ids = {sel.channel_id for sel in current_selections}
            
            # Determine which channels to add, update, or remove
            channels_to_add = selected_channel_ids - current_channel_ids
            channels_to_update = selected_channel_ids & current_channel_ids
            channels_to_remove = current_channel_ids - selected_channel_ids
            
            # Add new selections
            for channel_id in channels_to_add:
                selection_doc = {
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "is_selected": True,
                    "created_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC)
                }
                await db.user_channel_selections.insert_one(selection_doc)
                logger.info("Added channel selection for user %s, channel %s", user_id, channel_id)
            
            # Update existing selections to selected
            if channels_to_update:
                await db.user_channel_selections.update_many(
                    {
                        "user_id": user_id,
                        "channel_id": {"$in": list(channels_to_update)}
                    },
                    {
                        "$set": {
                            "is_selected": True,
                            "updated_at": datetime.now(UTC)
                        }
                    }
                )
                logger.info("Updated %d channel selections for user %s", len(channels_to_update), user_id)
            
            # Update channels to not selected (don't delete, just mark as not selected)
            if channels_to_remove:
                await db.user_channel_selections.update_many(
                    {
                        "user_id": user_id,
                        "channel_id": {"$in": list(channels_to_remove)}
                    },
                    {
                        "$set": {
                            "is_selected": False,
                            "updated_at": datetime.now(UTC)
                        }
                    }
                )
                logger.info("Removed %d channel selections for user %s", len(channels_to_remove), user_id)
            
            return True
            
        except Exception as e:
            logger.error("Error updating user channel selections: %s", e)
            return False

    async def toggle_channel_selection(self, user_id: int, channel_id: str) -> bool:
        """Toggle a single channel selection for user"""
        try:
            db = await self._get_db()
            
            # Check if selection exists
            existing = await db.user_channel_selections.find_one({
                "user_id": user_id,
                "channel_id": channel_id
            })
            
            if existing:
                # Toggle existing selection
                new_status = not existing.get("is_selected", True)
                result = await db.user_channel_selections.update_one(
                    {"_id": existing["_id"]},
                    {
                        "$set": {
                            "is_selected": new_status,
                            "updated_at": datetime.now(UTC)
                        }
                    }
                )
                return result.modified_count > 0
            else:
                # Create new selection
                selection_doc = {
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "is_selected": True,
                    "created_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC)
                }
                await db.user_channel_selections.insert_one(selection_doc)
                return True
                
        except Exception as e:
            logger.error("Error toggling channel selection: %s", e)
            return False

    async def is_channel_selected_by_user(self, user_id: int, channel_id: Union[int, str]) -> bool:
        """Check if user has selected a specific channel"""
        try:
            db = await self._get_db()
            
            # Normalize channel_id to standard format
            normalized_channel_id = channel_id_to_string(channel_id)
            
            # First, find the monitored channel by normalized channel_id to get its ObjectId
            monitored_channel = await db.monitored_channels.find_one({
                "channel_id": normalized_channel_id,
                "is_active": True
            })
            
            if not monitored_channel:
                logger.warning("Channel %s not found in monitored_channels", normalized_channel_id)
                return False
            
            # Use the ObjectId from monitored_channels
            monitored_channel_id = str(monitored_channel["_id"])
            
            # Check if user has selected this channel
            selection = await db.user_channel_selections.find_one({
                "user_id": user_id,
                "channel_id": monitored_channel_id,
                "is_selected": True
            })
            return selection is not None
            
        except Exception as e:
            logger.error("Error checking channel selection: %s", e)
            return False

    async def get_users_for_channel(self, channel_id: str) -> List[int]:
        """Get all users who have selected a specific channel"""
        try:
            db = await self._get_db()
            user_ids = []
            async for doc in db.user_channel_selections.find({
                "channel_id": channel_id,
                "is_selected": True
            }):
                user_ids.append(doc["user_id"])
            
            return user_ids
            
        except Exception as e:
            logger.error("Error getting users for channel: %s", e)
            return []
