"""
Admin API endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.bot.admin_decorators import is_admin

router = APIRouter()


class AdminRightsResponse(BaseModel):
    """Response model for admin rights check"""
    is_admin: bool
    user_id: int


@router.get("/check-rights", response_model=AdminRightsResponse)
async def check_admin_rights(user_id: int = Query(...)):
    """Check if user has admin rights"""
    try:
        admin_status = await is_admin(user_id)
        return AdminRightsResponse(
            is_admin=admin_status,
            user_id=user_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




