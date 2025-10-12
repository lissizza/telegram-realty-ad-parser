import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.models.monitored_channel import (
    MonitoredChannelCreate,
    MonitoredChannelResponse,
)
from app.services.monitored_channel_service import MonitoredChannelService
from app.bot.admin_decorators import is_admin

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
    user_id: int = Query(..., description="User ID (admin only)"),
    active_only: bool = Query(False, description="Show only active channels"),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Get all monitored channels (admin only)"""
    try:
        # Check if user has admin rights
        if not await is_admin(user_id):
            raise HTTPException(
                status_code=403,
                detail="Access denied. Only administrators can view monitored channels."
            )
        
        if active_only:
            channels = await service.get_active_channels()
        else:
            channels = await service.get_all_channels()
        
        return channels
        
    except Exception as e:
        logger.error("Error getting monitored channels: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=dict)
async def create_monitored_channel(
    channel_data: MonitoredChannelCreate,
    created_by: int = Query(..., description="Admin user ID who creates the channel"),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Create a new monitored channel (admin only)"""
    try:
        # Check if user has admin rights
        if not await is_admin(created_by):
            raise HTTPException(
                status_code=403, 
                detail="Only administrators can add channels. Please contact an admin to add channels."
            )
        
        channel_id = await service.create_channel(channel_data, created_by)
        
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
    user_id: int = Query(..., description="User ID (admin only)"),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Get monitored channel by ID (admin only)"""
    try:
        # Check if user has admin rights
        if not await is_admin(user_id):
            raise HTTPException(
                status_code=403,
                detail="Access denied. Only administrators can view channel details."
            )
        
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
    updated_by: int = Query(..., description="Admin user ID who updates the channel"),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Update monitored channel (admin only)"""
    try:
        # Check if user has admin rights
        if not await is_admin(updated_by):
            raise HTTPException(
                status_code=403, 
                detail="Only administrators can update channels."
            )
        
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
    deleted_by: int = Query(..., description="Admin user ID who deletes the channel"),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Delete monitored channel (admin only)"""
    try:
        # Check if user has admin rights
        if not await is_admin(deleted_by):
            raise HTTPException(
                status_code=403, 
                detail="Only administrators can delete channels."
            )
        
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
    toggled_by: int = Query(..., description="Admin user ID who toggles the channel"),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Toggle channel active status (admin only)"""
    try:
        # Check if user has admin rights
        if not await is_admin(toggled_by):
            raise HTTPException(
                status_code=403, 
                detail="Only administrators can toggle channel status."
            )
        
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
    created_by: int = Query(..., description="Admin user ID who creates the channel"),
    service: MonitoredChannelService = Depends(get_monitored_channel_service)
):
    """Quick add channel (admin only) - simplified endpoint"""
    try:
        # Check if user has admin rights
        if not await is_admin(created_by):
            raise HTTPException(
                status_code=403, 
                detail="Only administrators can add channels. Please contact an admin to add channels."
            )
        
        channel_data = MonitoredChannelCreate(channel_input=channel_input)
        channel_id = await service.create_channel(channel_data, created_by)
        
        if not channel_id:
            raise HTTPException(status_code=400, detail="Failed to create channel subscription")
        
        return {"message": "Channel added successfully", "channel_id": channel_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error quick adding channel: %s", e)
        raise HTTPException(status_code=500, detail=str(e))





