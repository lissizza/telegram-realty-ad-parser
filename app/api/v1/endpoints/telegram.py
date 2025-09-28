from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.telegram_service import TelegramService

router = APIRouter()


class StartMonitoringRequest(BaseModel):
    """Request model for starting monitoring"""
    pass


class StopMonitoringRequest(BaseModel):
    """Request model for stopping monitoring"""
    pass


class RefilterRequest(BaseModel):
    """Request model for refiltering ads"""
    count: int
    user_id: Optional[int] = None


class ReprocessRequest(BaseModel):
    """Request model for reprocessing messages"""
    channel_id: Optional[int] = None
    limit: int = 50


@router.post("/start-monitoring")
async def start_monitoring(request: StartMonitoringRequest):
    """Start monitoring Telegram channels"""
    try:
        telegram_service = TelegramService()
        await telegram_service.start_monitoring()
        return {"message": "Monitoring started successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop-monitoring")
async def stop_monitoring(request: StopMonitoringRequest):
    """Stop monitoring Telegram channels"""
    try:
        telegram_service = TelegramService()
        await telegram_service.stop_monitoring()
        return {"message": "Monitoring stopped successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    """Get bot status"""
    try:
        telegram_service = TelegramService()
        status = await telegram_service.get_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring-status")
async def get_monitoring_status():
    """Get current monitoring status"""
    try:
        telegram_service = TelegramService()
        return {
            "is_monitoring": telegram_service.is_monitoring,
            "status": "active" if telegram_service.is_monitoring else "inactive"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refilter")
async def refilter_ads(request: RefilterRequest):
    """Refilter existing ads without reprocessing"""
    try:
        from app.services import get_telegram_service
        telegram_service = get_telegram_service()
        result = await telegram_service.refilter_ads(request.count, request.user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 