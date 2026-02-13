import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.models.token import TokenData
from app.models.user_channel_selection import (
    UserChannelSelectionBulkUpdate,
    UserChannelSelectionResponse,
)
from app.services.user_channel_selection_service import UserChannelSelectionService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_user_channel_selection_service() -> UserChannelSelectionService:
    """Dependency to get UserChannelSelectionService"""
    return UserChannelSelectionService()


@router.options("/")
async def options_user_channel_selections():
    """Handle OPTIONS requests for CORS preflight"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )


@router.options("/{user_id}")
async def options_user_channel_selections_by_user(user_id: int):
    """Handle OPTIONS requests for CORS preflight"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )


@router.get("/user/{user_id}", response_model=List[UserChannelSelectionResponse])
async def get_user_channel_selections(
    user_id: int,
    current_user: TokenData = Depends(get_current_user),
    service: UserChannelSelectionService = Depends(get_user_channel_selection_service)
):
    """Get user's channel selections"""
    if current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only view your own channel selections")
    try:
        selections = await service.get_user_selected_channels(user_id)
        return selections

    except Exception as e:
        logger.error("Error getting user channel selections: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/available", response_model=dict)
async def get_available_channels_for_user(
    user_id: int,
    current_user: TokenData = Depends(get_current_user),
    service: UserChannelSelectionService = Depends(get_user_channel_selection_service)
):
    """Get all available channels for user with selection status"""
    if current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only view your own channel selections")
    try:
        channels, auto_selected = await service.get_available_channels_for_user(user_id)
        return {"channels": channels, "auto_selected": auto_selected}

    except Exception as e:
        logger.error("Error getting available channels for user: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/user/{user_id}/bulk", response_model=dict)
async def update_user_channel_selections(
    user_id: int,
    update_data: UserChannelSelectionBulkUpdate,
    current_user: TokenData = Depends(get_current_user),
    service: UserChannelSelectionService = Depends(get_user_channel_selection_service)
):
    """Update user's channel selections (bulk update)"""
    if current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only update your own channel selections")
    try:
        update_data.user_id = user_id

        success = await service.update_user_channel_selections(update_data)

        if not success:
            raise HTTPException(status_code=400, detail="Failed to update channel selections")

        return {"message": "Channel selections updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating user channel selections: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/{user_id}/toggle/{channel_id}", response_model=dict)
async def toggle_channel_selection(
    user_id: int,
    channel_id: str,
    current_user: TokenData = Depends(get_current_user),
    service: UserChannelSelectionService = Depends(get_user_channel_selection_service)
):
    """Toggle a single channel selection for user"""
    if current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only toggle your own channel selections")
    try:
        success = await service.toggle_channel_selection(user_id, channel_id)

        if not success:
            raise HTTPException(status_code=400, detail="Failed to toggle channel selection")

        return {"message": "Channel selection toggled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error toggling channel selection: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channel/{channel_id}/users", response_model=List[int])
async def get_users_for_channel(
    channel_id: str,
    current_user: TokenData = Depends(get_current_user),
    service: UserChannelSelectionService = Depends(get_user_channel_selection_service)
):
    """Get all users who have selected a specific channel"""
    try:
        user_ids = await service.get_users_for_channel(channel_id)
        return user_ids

    except Exception as e:
        logger.error("Error getting users for channel: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# Simple endpoint for quick channel selection
class QuickChannelSelectionRequest(BaseModel):
    selected_channel_ids: List[str]


@router.post("/quick-update", response_model=dict)
async def quick_update_channel_selections(
    request: QuickChannelSelectionRequest,
    current_user: TokenData = Depends(get_current_user),
    service: UserChannelSelectionService = Depends(get_user_channel_selection_service)
):
    """Quick update channel selections with just selected channel IDs"""
    try:
        update_data = UserChannelSelectionBulkUpdate(
            user_id=current_user.user_id,
            selected_channel_ids=request.selected_channel_ids
        )

        success = await service.update_user_channel_selections(update_data)

        if not success:
            raise HTTPException(status_code=400, detail="Failed to update channel selections")

        return {"message": "Channel selections updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error quick updating channel selections: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
