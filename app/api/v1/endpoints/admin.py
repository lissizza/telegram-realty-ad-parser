"""
Admin API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_current_user, get_current_super_admin
from app.bot.admin_decorators import is_admin
from app.models.token import TokenData
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
async def check_admin_rights(current_user: TokenData = Depends(get_current_user)):
    """Check if user has admin rights"""
    try:
        admin_status = await is_admin(current_user.user_id)
        return AdminRightsResponse(
            is_admin=admin_status,
            user_id=current_user.user_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/llm-quota/status", response_model=QuotaStatusResponse)
async def get_quota_status(current_user: TokenData = Depends(get_current_super_admin)):
    """Get LLM quota status (super admin only)"""
    try:
        status = llm_quota_service.get_status()
        return QuotaStatusResponse(**status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/llm-quota/check-balance", response_model=BalanceCheckResponse)
async def check_balance_manually(current_user: TokenData = Depends(get_current_super_admin)):
    """Manually trigger LLM balance check (super admin only)"""
    try:
        balance_available = await llm_quota_service.check_balance()
        quota_exceeded = llm_quota_service.is_quota_exceeded()

        if balance_available:
            message = "Balance check successful - quota is available"
        else:
            message = "Balance check failed - quota still exceeded"

        return BalanceCheckResponse(
            balance_available=balance_available,
            quota_exceeded=quota_exceeded,
            message=message
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
