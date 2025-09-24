from typing import List

from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId

from app.models.incoming_message import IncomingMessage
from app.db.mongodb import mongodb

router = APIRouter()


@router.get("/", response_model=List[IncomingMessage])
async def get_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    channel_id: int = None,
):
    """Get posts with pagination and optional channel filtering"""
    db = mongodb.get_database()
    query = {}
    if channel_id:
        query["channel_id"] = channel_id
    
    posts = []
    cursor = db.incoming_messages.find(query).skip(skip).limit(limit).sort("date", -1)
    async for post_doc in cursor:
        post_doc["id"] = str(post_doc["_id"])
        posts.append(IncomingMessage(**post_doc))
    return posts


@router.get("/{post_id}", response_model=IncomingMessage)
async def get_post(post_id: str):
    """Get a specific post"""
    db = mongodb.get_database()
    post_doc = await db.incoming_messages.find_one({"_id": ObjectId(post_id)})
    if not post_doc:
        raise HTTPException(status_code=404, detail="Post not found")
    post_doc["id"] = str(post_doc["_id"])
    return IncomingMessage(**post_doc)


@router.delete("/{post_id}")
async def delete_post(post_id: str):
    """Delete a post"""
    db = mongodb.get_database()
    result = await db.incoming_messages.delete_one({"_id": ObjectId(post_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post deleted successfully"} 