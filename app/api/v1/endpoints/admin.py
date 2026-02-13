"""
Admin API endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.bot.admin_decorators import is_admin, is_super_admin
from app.services.llm_quota_service import llm_quota_service

router = APIRouter()


class AdminRightsResponse(BaseModel):
    """Response model for admin rights check"""
    is_admin: bool
    user_id: int


class QuotaStatusResponse(BaseModel):
    """Response model for LLM quota status"""
    quota_exceeded: bool
    last_quota_error_time: str | None
    last_balance_check_time: str | None
    balance_check_interval_minutes: float


class BalanceCheckResponse(BaseModel):
    """Response model for balance check"""
    balance_available: bool
    quota_exceeded: bool
    message: str


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


@router.get("/llm-quota/status", response_model=QuotaStatusResponse)
async def get_quota_status(user_id: int = Query(...)):
    """Get LLM quota status (super admin only)"""
    try:
        # Check if user is super admin
        if not await is_super_admin(user_id):
            raise HTTPException(status_code=403, detail="Only super admins can check quota status")
        
        status = llm_quota_service.get_status()
        return QuotaStatusResponse(**status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/llm-quota/check-balance", response_model=BalanceCheckResponse)
async def check_balance_manually(user_id: int = Query(...)):
    """Manually trigger LLM balance check (super admin only)"""
    try:
        # Check if user is super admin
        if not await is_super_admin(user_id):
            raise HTTPException(status_code=403, detail="Only super admins can check balance")
        
        # Perform balance check
        balance_available = await llm_quota_service.check_balance()
        quota_exceeded = llm_quota_service.is_quota_exceeded()
        
        if balance_available:
            message = "✅ Balance check successful - quota is available"
        else:
            message = "❌ Balance check failed - quota still exceeded"
        
        return BalanceCheckResponse(
            balance_available=balance_available,
            quota_exceeded=quota_exceeded,
            message=message
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




