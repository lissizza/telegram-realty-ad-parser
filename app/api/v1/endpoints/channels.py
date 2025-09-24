from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from bson import ObjectId

from app.db.mongodb import mongodb

router = APIRouter()


class ChannelCreate(BaseModel):
    username: str
    title: str
    description: Optional[str] = ""


class ChannelResponse(BaseModel):
    id: str
    username: str
    title: str
    description: str
    is_active: bool
    created_at: str
    updated_at: str


@router.get("/", response_model=List[ChannelResponse])
async def get_channels():
    """Get all monitored channels"""
    try:
        db = mongodb.get_database()
        channels = []
        
        async for channel_doc in db.channels.find():
            channel_doc["id"] = str(channel_doc["_id"])
            channels.append(ChannelResponse(**channel_doc))
        
        return channels
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=ChannelResponse)
async def create_channel(channel: ChannelCreate):
    """Add a new channel to monitor"""
    try:
        db = mongodb.get_database()
        
        # Check if channel already exists
        existing = await db.channels.find_one({"username": channel.username})
        if existing:
            raise HTTPException(status_code=400, detail="Channel already exists")
        
        channel_data = {
            "username": channel.username,
            "title": channel.title,
            "description": channel.description,
            "is_active": True,
            "created_at": "2024-01-01T00:00:00",  # Will be set by MongoDB
            "updated_at": "2024-01-01T00:00:00"
        }
        
        result = await db.channels.insert_one(channel_data)
        channel_data["id"] = str(result.inserted_id)
        
        return ChannelResponse(**channel_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{channel_id}/activate")
async def activate_channel(channel_id: str):
    """Activate channel monitoring"""
    try:
        db = mongodb.get_database()
        
        if not ObjectId.is_valid(channel_id):
            raise HTTPException(status_code=400, detail="Invalid channel ID")
        
        result = await db.channels.update_one(
            {"_id": ObjectId(channel_id)},
            {"$set": {"is_active": True, "updated_at": "2024-01-01T00:00:00"}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Channel not found")
        
        return {"message": "Channel activated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{channel_id}/deactivate")
async def deactivate_channel(channel_id: str):
    """Deactivate channel monitoring"""
    try:
        db = mongodb.get_database()
        
        if not ObjectId.is_valid(channel_id):
            raise HTTPException(status_code=400, detail="Invalid channel ID")
        
        result = await db.channels.update_one(
            {"_id": ObjectId(channel_id)},
            {"$set": {"is_active": False, "updated_at": "2024-01-01T00:00:00"}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Channel not found")
        
        return {"message": "Channel deactivated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{channel_id}")
async def delete_channel(channel_id: str):
    """Delete a channel"""
    try:
        db = mongodb.get_database()
        
        if not ObjectId.is_valid(channel_id):
            raise HTTPException(status_code=400, detail="Invalid channel ID")
        
        result = await db.channels.delete_one({"_id": ObjectId(channel_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Channel not found")
        
        return {"message": "Channel deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))