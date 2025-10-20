"""
API endpoints for user filter matches
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.models.user_filter_match import UserFilterMatch
from app.services.filter_service import FilterService

router = APIRouter()


class UserFilterMatchResponse(BaseModel):
    """Response model for user filter match"""
    id: str
    user_id: int
    filter_id: str
    real_estate_ad_id: str
    matched_at: str
    forwarded: bool
    forwarded_at: Optional[str] = None
    status: str


def get_filter_service() -> FilterService:
    """Get filter service instance"""
    return FilterService()


@router.get("/", response_model=List[UserFilterMatchResponse])
async def get_user_filter_matches(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    forwarded: Optional[bool] = Query(None, description="Filter by forwarded status"),
    limit: int = Query(100, ge=1, le=1000, description="Limit number of results"),
    service: FilterService = Depends(get_filter_service)
):
    """Get user filter matches with optional filtering"""
    try:
        if user_id:
            matches = await service.get_matches_for_user(user_id, limit)
        else:
            # For now, we don't have a method to get all matches
            # This would need to be implemented in the service
            raise HTTPException(status_code=400, detail="user_id parameter is required")
        
        # Filter by forwarded status if specified
        if forwarded is not None:
            matches = [m for m in matches if m.forwarded == forwarded]
        
        # Convert to response format
        response = []
        for match in matches:
            response.append(UserFilterMatchResponse(
                id=match.id or "",
                user_id=match.user_id,
                filter_id=match.filter_id,
                real_estate_ad_id=match.real_estate_ad_id,
                matched_at=match.matched_at.isoformat(),
                forwarded=match.forwarded,
                forwarded_at=match.forwarded_at.isoformat() if match.forwarded_at else None,
                status=match.status
            ))
        
        return response
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error("Error getting user filter matches: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/unforwarded", response_model=List[UserFilterMatchResponse])
async def get_unforwarded_matches(
    user_id: int = Query(..., description="User ID to get unforwarded matches for"),
    service: FilterService = Depends(get_filter_service)
):
    """Get all unforwarded matches for a specific user"""
    try:
        matches = await service.get_unforwarded_matches_for_user(user_id)
        
        response = []
        for match in matches:
            response.append(UserFilterMatchResponse(
                id=match.id or "",
                user_id=match.user_id,
                filter_id=match.filter_id,
                real_estate_ad_id=match.real_estate_ad_id,
                matched_at=match.matched_at.isoformat(),
                forwarded=match.forwarded,
                forwarded_at=match.forwarded_at.isoformat() if match.forwarded_at else None,
                status=match.status
            ))
        
        return response
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error("Error getting unforwarded matches for user %s: %s", user_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{match_id}/mark-forwarded", response_model=dict)
async def mark_match_as_forwarded(
    match_id: str,
    service: FilterService = Depends(get_filter_service)
):
    """Mark a user filter match as forwarded"""
    try:
        success = await service.mark_as_forwarded(match_id)
        if success:
            return {"message": "Match marked as forwarded successfully"}
        else:
            raise HTTPException(status_code=404, detail="Match not found")
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error("Error marking match %s as forwarded: %s", match_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/ad/{real_estate_ad_id}", response_model=List[UserFilterMatchResponse])
async def get_matches_for_ad(
    real_estate_ad_id: str,
    service: FilterService = Depends(get_filter_service)
):
    """Get all matches for a specific real estate ad"""
    try:
        matches = await service.get_matches_for_ad(real_estate_ad_id)
        
        response = []
        for match in matches:
            response.append(UserFilterMatchResponse(
                id=match.id or "",
                user_id=match.user_id,
                filter_id=match.filter_id,
                real_estate_ad_id=match.real_estate_ad_id,
                matched_at=match.matched_at.isoformat(),
                forwarded=match.forwarded,
                forwarded_at=match.forwarded_at.isoformat() if match.forwarded_at else None,
                status=match.status
            ))
        
        return response
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error("Error getting matches for ad %s: %s", real_estate_ad_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e













