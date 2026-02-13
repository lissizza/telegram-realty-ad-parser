import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.api.dependencies import get_current_admin
from app.models.monitored_channel import (
    MonitoredChannelCreate,
    MonitoredChannelResponse,
)
from app.models.token import TokenData
from app.services.monitored_channel_service import MonitoredChannelService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_monitored_channel_service() -> MonitoredChannelService:
    """Dependency to get MonitoredChannelService"""
    return MonitoredChannelService()


@router.options("/")
async def options_monitored_channels():
    """Handle OPTIONS requests for CORS preflight"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )


@router.options("/{channel_id}")
async def options_monitored_channel_by_id(channel_id: str):
    """Handle OPTIONS requests for CORS preflight"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )


@router.get("/", response_model=List[MonitoredChannelResponse])
async def get_monitored_channels(
    active_only: bool = Query(False, description="Show only active channels"),
    current_user: TokenData = Depends(get_current_admin),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Get all monitored channels (admin only)"""
    try:
        if active_only:
            channels = await service.get_active_channels()
        else:
            channels = await service.get_all_channels()

        return channels

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting monitored channels: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=dict)
async def create_monitored_channel(
    channel_data: MonitoredChannelCreate,
    current_user: TokenData = Depends(get_current_admin),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Create a new monitored channel (admin only)"""
    try:
        channel_id = await service.create_channel(channel_data, current_user.user_id)

        if not channel_id:
            raise HTTPException(status_code=400, detail="Failed to create channel subscription")

        return {"message": "Channel added successfully", "channel_id": channel_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating monitored channel: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{channel_id}", response_model=MonitoredChannelResponse)
async def get_monitored_channel(
    channel_id: str,
    current_user: TokenData = Depends(get_current_admin),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Get monitored channel by ID (admin only)"""
    try:
        channel = await service.get_channel_by_id(channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")

        return channel

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting monitored channel: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{channel_id}", response_model=dict)
async def update_monitored_channel(
    channel_id: str,
    update_data: dict,
    current_user: TokenData = Depends(get_current_admin),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Update monitored channel (admin only)"""
    try:
        success = await service.update_channel(channel_id, update_data)
        if not success:
            raise HTTPException(status_code=404, detail="Channel not found or no changes made")

        return {"message": "Channel updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating monitored channel: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{channel_id}", response_model=dict)
async def delete_monitored_channel(
    channel_id: str,
    current_user: TokenData = Depends(get_current_admin),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Delete monitored channel (admin only)"""
    try:
        success = await service.delete_channel(channel_id)
        if not success:
            raise HTTPException(status_code=404, detail="Channel not found")

        return {"message": "Channel deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting monitored channel: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{channel_id}/toggle", response_model=dict)
async def toggle_channel_status(
    channel_id: str,
    current_user: TokenData = Depends(get_current_admin),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Toggle channel active status (admin only)"""
    try:
        success = await service.toggle_channel_status(channel_id)
        if not success:
            raise HTTPException(status_code=404, detail="Channel not found")

        return {"message": "Channel status toggled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error toggling channel status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# Quick add endpoint for backward compatibility
@router.post("/quick-add", response_model=dict)
async def quick_add_channel(
    channel_input: str = Query(..., description="Channel URL, username, or ID"),
    current_user: TokenData = Depends(get_current_admin),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Quick add channel (admin only) - simplified endpoint"""
    try:
        channel_data = MonitoredChannelCreate(channel_input=channel_input)
        channel_id = await service.create_channel(channel_data, current_user.user_id)

        if not channel_id:
            raise HTTPException(status_code=400, detail="Failed to create channel subscription")

        return {"message": "Channel added successfully", "channel_id": channel_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error quick adding channel: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
