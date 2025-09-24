from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Dict, Any

from app.db.mongodb import mongodb

router = APIRouter()


class StatisticsResponse(BaseModel):
    total_posts: int
    parsed_ads: int
    spam_filtered: int
    media_only: int
    non_real_estate: int
    active_channels: int
    active_search_settings: int
    matched_filters: int
    forwarded_ads: int  # Ads that were actually forwarded to user
    parsing_status: str
    bot_status: str
    total_llm_cost: float
    avg_cost_per_ad: float
    last_updated: str


@router.get("/", response_model=StatisticsResponse)
async def get_statistics():
    """Get parsing statistics"""
    try:
        db = mongodb.get_database()
        
        # Count total posts
        total_posts = await db.incoming_messages.count_documents({})
        
        # Count parsed real estate ads
        parsed_ads = await db.real_estate_ads.count_documents({})
        
        # Spam filtering removed - LLM handles it via is_real_estate
        
        # Media-only posts are no longer saved to database
        
        # Count non-real-estate posts
        non_real_estate = await db.incoming_messages.count_documents({"is_real_estate": False})
        
        # Count active channels
        active_channels = await db.channels.count_documents({"is_active": True})
        
        # Count active search settings
        active_search_settings = await db.search_settings.count_documents({"is_active": True})
        
        # Count matched filters (ads that matched any filter)
        matched_filters = await db.real_estate_ads.count_documents({
            "matched_filters": {"$exists": True, "$ne": []}
        })
        
        # Count forwarded ads (ads that were actually sent to user)
        forwarded_ads = await db.outgoing_posts.count_documents({})
        
        # Get LLM cost statistics
        llm_costs = await db.llm_costs.find({}).to_list(length=None)
        total_llm_cost = sum(cost["cost_usd"] for cost in llm_costs)
        # Calculate average cost per parsed ad, not per cost record
        avg_cost_per_ad = total_llm_cost / parsed_ads if parsed_ads > 0 else 0.0
        
        # Get parsing status (simplified - in real app would check actual service status)
        parsing_status = "active" if active_channels > 0 else "inactive"
        
        # Bot status (simplified)
        bot_status = "active"  # In real app, check actual bot status
        
        return StatisticsResponse(
            total_posts=total_posts,
            parsed_ads=parsed_ads,
            spam_filtered=0,  # Removed - LLM handles spam detection
            media_only=0,  # No longer saved to database
            non_real_estate=non_real_estate,
            active_channels=active_channels,
            active_search_settings=active_search_settings,
            matched_filters=matched_filters,
            forwarded_ads=forwarded_ads,
            parsing_status=parsing_status,
            bot_status=bot_status,
            total_llm_cost=total_llm_cost,
            avg_cost_per_ad=avg_cost_per_ad,
            last_updated=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detailed")
async def get_detailed_statistics():
    """Get detailed statistics with message status breakdown"""
    try:
        db = mongodb.get_database()
        
        # Get status breakdown
        status_pipeline = [
            {"$group": {
                "_id": "$processing_status",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        status_breakdown = await db.incoming_messages.aggregate(status_pipeline).to_list(length=None)
        status_counts = {item["_id"]: item["count"] for item in status_breakdown}
        
        # Get recent activity (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_activity = await db.incoming_messages.count_documents({
            "created_at": {"$gte": yesterday}
        })
        
        # Get error messages
        error_posts = await db.incoming_messages.find(
            {"processing_status": "error"},
            {"id": 1, "parsing_errors": 1, "created_at": 1}
        ).sort("created_at", -1).limit(10).to_list(length=None)
        
        # Get channel breakdown
        channel_pipeline = [
            {"$group": {
                "_id": "$channel_title",
                "total_posts": {"$sum": 1},
                "parsed_ads": {"$sum": {"$cond": [{"$eq": ["$status", "parsed"]}, 1, 0]}},
                "forwarded_ads": {"$sum": {"$cond": [{"$eq": ["$status", "forwarded"]}, 1, 0]}}
            }},
            {"$sort": {"total_posts": -1}}
        ]
        
        channel_breakdown = await db.incoming_messages.aggregate(channel_pipeline).to_list(length=None)
        
        return {
            "status_breakdown": status_counts,
            "recent_activity": {
                "last_24h_posts": recent_activity
            },
            "channel_breakdown": channel_breakdown,
            "recent_errors": error_posts,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
