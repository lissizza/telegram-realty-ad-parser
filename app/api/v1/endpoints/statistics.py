from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Dict, Any

from app.db.mongodb import mongodb

router = APIRouter()


class StatisticsResponse(BaseModel):
    total_posts: int
    parsed_ads: int
    non_real_estate: int
    duplicates: int  # Messages marked as duplicates
    active_channels: int
    registered_users: int  # Total registered users
    matched_filters: int  # Total ads that matched any filter (all users)
    forwarded_ads: int  # Total ads forwarded to all users
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
        
        # Count non-real-estate posts
        non_real_estate = await db.incoming_messages.count_documents({"is_real_estate": False})
        
        # Count duplicate messages
        duplicates = await db.incoming_messages.count_documents({"processing_status": "duplicate"})
        
        # Count active channels from monitored channels
        active_channels = await db.monitored_channels.count_documents({"is_active": True})
        
        # Count registered users (admin users)
        registered_users = await db.admin_users.count_documents({"is_active": True})
        
        # Count forwarded ads (ads that were actually sent to user)
        forwarded_ads = await db.outgoing_posts.count_documents({})
        
        # Count ads that were forwarded (have FORWARDED status)
        forwarded_ads_by_status = await db.real_estate_ads.count_documents({
            "processing_status": "forwarded"
        })
        
        # Use the higher count as matched_filters (should be the same)
        matched_filters = max(forwarded_ads, forwarded_ads_by_status)
        
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
            non_real_estate=non_real_estate,
            duplicates=duplicates,
            active_channels=active_channels,
            registered_users=registered_users,
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
        
        # Get status breakdown for incoming messages
        status_pipeline = [
            {"$group": {
                "_id": "$processing_status",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        status_breakdown = await db.incoming_messages.aggregate(status_pipeline).to_list(length=None)
        status_counts = {item["_id"]: item["count"] for item in status_breakdown}
        
        # Get real estate ad status breakdown
        ad_status_pipeline = [
            {"$group": {
                "_id": "$processing_status",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        ad_status_breakdown = await db.real_estate_ads.aggregate(ad_status_pipeline).to_list(length=None)
        ad_status_counts = {item["_id"]: item["count"] for item in ad_status_breakdown}
        
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
            "incoming_message_status_breakdown": status_counts,
            "real_estate_ad_status_breakdown": ad_status_counts,
            "recent_activity": {
                "last_24h_posts": recent_activity
            },
            "channel_breakdown": channel_breakdown,
            "recent_errors": error_posts,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
