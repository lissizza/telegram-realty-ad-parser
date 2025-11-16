from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

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


class DailyStatsResponse(BaseModel):
    labels: List[str]
    messages: List[int]
    ads: List[int]


class LLMCostsResponse(BaseModel):
    total_cost: float
    today_cost: float
    avg_daily_cost: float
    requests: int
    daily_costs: List[float]
    labels: List[str]


@router.get("/daily", response_model=DailyStatsResponse)
async def get_daily_statistics():
    """Get daily statistics for the last 7 days"""
    try:
        db = mongodb.get_database()
        
        labels = []
        messages = []
        ads = []
        
        for i in range(6, -1, -1):  # Last 7 days
            date = datetime.now(timezone.utc) - timedelta(days=i)
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Count messages for this day
            message_count = await db.incoming_messages.count_documents({
                "created_at": {"$gte": start_of_day, "$lte": end_of_day}
            })
            
            # Count real estate ads for this day
            ad_count = await db.real_estate_ads.count_documents({
                "created_at": {"$gte": start_of_day, "$lte": end_of_day}
            })
            
            labels.append(date.strftime("%d.%m"))
            messages.append(message_count)
            ads.append(ad_count)
        
        return DailyStatsResponse(
            labels=labels,
            messages=messages,
            ads=ads
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/llm-costs", response_model=LLMCostsResponse)
async def get_llm_costs():
    """Get LLM costs statistics"""
    try:
        db = mongodb.get_database()
        
        # Get all LLM costs
        costs_cursor = db.llm_costs.find({}).sort("created_at", 1)
        all_costs = await costs_cursor.to_list(length=None)
        
        if not all_costs:
            # Return empty data if no costs found
            return LLMCostsResponse(
                total_cost=0.0,
                today_cost=0.0,
                avg_daily_cost=0.0,
                requests=0,
                daily_costs=[0.0] * 7,
                labels=[(datetime.now(timezone.utc) - timedelta(days=i)).strftime("%d.%m") for i in range(6, -1, -1)]
            )
        
        # Calculate total cost
        total_cost = sum(cost.get("cost_usd", 0) for cost in all_costs)
        
        # Calculate today's cost
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_costs = [cost for cost in all_costs 
                      if cost.get("created_at") and cost.get("created_at").replace(tzinfo=timezone.utc) >= today]
        today_cost = sum(cost.get("cost_usd", 0) for cost in today_costs)
        
        # Calculate daily costs for last 7 days
        daily_costs = []
        labels = []
        
        for i in range(6, -1, -1):
            date = datetime.now(timezone.utc) - timedelta(days=i)
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            day_costs = [cost for cost in all_costs 
                        if cost.get("created_at") and 
                        start_of_day <= cost.get("created_at").replace(tzinfo=timezone.utc) <= end_of_day]
            day_total = sum(cost.get("cost_usd", 0) for cost in day_costs)
            
            daily_costs.append(round(day_total, 2))
            labels.append(date.strftime("%d.%m"))
        
        # Calculate average daily cost
        avg_daily_cost = total_cost / max(len(all_costs), 1) if all_costs else 0.0
        
        return LLMCostsResponse(
            total_cost=round(total_cost, 2),
            today_cost=round(today_cost, 2),
            avg_daily_cost=round(avg_daily_cost, 2),
            requests=len(all_costs),
            daily_costs=daily_costs,
            labels=labels
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ChannelActivityResponse(BaseModel):
    channel_id: str
    channel_title: str
    channel_username: str
    message_count: int
    ad_count: int


@router.get("/channel-activity", response_model=List[ChannelActivityResponse])
async def get_channel_activity():
    """Get channel activity statistics"""
    try:
        db = mongodb.get_database()
        
        # Get all active monitored channels
        channels = []
        async for channel_doc in db.monitored_channels.find({"is_active": True}):
            channel_id = channel_doc.get("channel_id")
            if not channel_id:
                continue
                
            # Count messages from this channel
            message_count = await db.incoming_messages.count_documents({
                "channel_id": int(channel_id)
            })
            
            # Count real estate ads from this channel
            ad_count = await db.real_estate_ads.count_documents({
                "channel_id": int(channel_id)
            })
            
            channels.append(ChannelActivityResponse(
                channel_id=channel_id,
                channel_title=channel_doc.get("channel_title", "Unknown"),
                channel_username=channel_doc.get("channel_username", "unknown"),
                message_count=message_count,
                ad_count=ad_count
            ))
        
        # Sort by message count (most active first)
        channels.sort(key=lambda x: x.message_count, reverse=True)
        
        return channels[:5]  # Return top 5 channels
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
