from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.models.user_channel_subscription import (
    UserChannelSubscriptionCreate,
    UserChannelSubscriptionResponse,
)
from app.services.user_channel_subscription_service import (
    UserChannelSubscriptionService,
)

router = APIRouter()


def get_user_channel_subscription_service() -> UserChannelSubscriptionService:
    """Dependency to get UserChannelSubscriptionService"""
    return UserChannelSubscriptionService()


@router.options("/")
async def options_user_subscriptions():
    """Handle OPTIONS requests for CORS preflight"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )


@router.options("/{subscription_id}")
async def options_user_subscription_by_id(subscription_id: str):
    """Handle OPTIONS requests for CORS preflight"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )


@router.get("/debug")
async def debug_subscriptions():
    """Debug endpoint to check subscriptions directly"""
    try:
        from app.db.mongodb import mongodb

        # Check MongoDB connection status
        connection_status = {
            "mongodb_client": mongodb.client is not None,
            "mongodb_database": mongodb.get_database() is not None
        }
        
        # Try to connect if not connected
        if mongodb.client is None:
            await mongodb.connect_to_mongo()
        
        db = mongodb.get_database()
        if db is None:
            return {"error": "Database not available", "connection_status": connection_status}
        
        # Check all subscriptions
        all_subscriptions = []
        async for sub in db.user_channel_subscriptions.find():
            all_subscriptions.append({
                "id": str(sub["_id"]),
                "user_id": sub["user_id"],
                "channel_username": sub.get("channel_username"),
                "is_active": sub.get("is_active", True)
            })
        
        return {
            "connection_status": connection_status,
            "total_subscriptions": len(all_subscriptions),
            "subscriptions": all_subscriptions
        }
        
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}

@router.get("/", response_model=List[UserChannelSubscriptionResponse])
async def get_user_subscriptions(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    active_only: bool = Query(False, description="Show only active subscriptions"),
    service: UserChannelSubscriptionService = Depends(get_user_channel_subscription_service)
):
    """Get user channel subscriptions"""
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Getting subscriptions for user_id=%s, active_only=%s", user_id, active_only)
        
        # Debug: Check MongoDB connection
        from app.db.mongodb import mongodb
        logger.info("MongoDB client status: %s", mongodb.client is not None)
        logger.info("MongoDB database status: %s", mongodb.get_database() is not None)
        
        if user_id:
            if active_only:
                subscriptions = await service.get_active_user_subscriptions(user_id)
                logger.info("Found %s active subscriptions for user %s", len(subscriptions), user_id)
            else:
                subscriptions = await service.get_user_subscriptions(user_id)
                logger.info("Found %s subscriptions for user %s", len(subscriptions), user_id)
        else:
            subscriptions = await service.get_all_active_subscriptions()
            logger.info("Found %s total active subscriptions", len(subscriptions))
        
        return subscriptions
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("Error getting subscriptions: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=dict)
async def create_user_subscription(
    subscription: UserChannelSubscriptionCreate,
    service: UserChannelSubscriptionService = Depends(get_user_channel_subscription_service)
):
    """Create a new user channel subscription"""
    try:
        subscription_id = await service.create_subscription(subscription)
        
        if not subscription_id:
            raise HTTPException(status_code=400, detail="Failed to create subscription")
        
        # Update channel monitoring to include new subscription
        try:
            from app.services import get_telegram_service
            telegram_service = get_telegram_service()
            await telegram_service.update_channel_monitoring()
            logger.info("Updated channel monitoring after creating subscription %s", subscription_id)
        except Exception as e:
            logger.warning("Failed to update channel monitoring: %s", e)
        
        return {
            "message": "Subscription created successfully",
            "subscription_id": subscription_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{subscription_id}", response_model=dict)
async def update_user_subscription(
    subscription_id: str,
    updates: dict,
    service: UserChannelSubscriptionService = Depends(get_user_channel_subscription_service)
):
    """Update a user channel subscription"""
    try:
        success = await service.update_subscription(subscription_id, updates)
        
        if not success:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        return {"message": "Subscription updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{subscription_id}/toggle", response_model=dict)
async def toggle_user_subscription(
    subscription_id: str,
    service: UserChannelSubscriptionService = Depends(get_user_channel_subscription_service)
):
    """Toggle subscription active status"""
    try:
        success = await service.toggle_subscription_active(subscription_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        return {"message": "Subscription status toggled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{subscription_id}", response_model=dict)
async def delete_user_subscription(
    subscription_id: str,
    service: UserChannelSubscriptionService = Depends(get_user_channel_subscription_service)
):
    """Delete a user channel subscription"""
    try:
        success = await service.delete_subscription(subscription_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        return {"message": "Subscription deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Simple endpoint for quick channel addition
class QuickAddRequest(BaseModel):
    user_id: int
    channel_input: str
    topic_id: Optional[int] = None


@router.post("/quick-add", response_model=dict)
async def quick_add_channel(
    request: QuickAddRequest,
    service: UserChannelSubscriptionService = Depends(get_user_channel_subscription_service)
):
    """Quick add a channel subscription with just user_id and channel input"""
    try:
        subscription_data = UserChannelSubscriptionCreate(
            user_id=request.user_id,
            channel_input=request.channel_input,
            topic_id=request.topic_id
        )
        
        subscription_id = await service.create_subscription(subscription_data)
        
        if not subscription_id:
            raise HTTPException(status_code=400, detail="Failed to create subscription")
        
        # Update channel monitoring to include new subscription
        try:
            from app.services import get_telegram_service
            telegram_service = get_telegram_service()
            await telegram_service.update_channel_monitoring()
            logger.info("Updated channel monitoring after quick adding subscription %s", subscription_id)
        except Exception as e:
            logger.warning("Failed to update channel monitoring: %s", e)
        
        return {
            "message": "Channel subscription created successfully",
            "subscription_id": subscription_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
