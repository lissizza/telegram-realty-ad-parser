from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()


class APIConfig(BaseModel):
    """API configuration for frontend"""
    api_base_url: str
    simple_filters_url: str
    channel_management_url: str
    search_settings_url: str


@router.get("/api-config", response_model=APIConfig)
async def get_api_config():
    """Get API configuration for frontend JavaScript"""
    return APIConfig(
        api_base_url=settings.API_BASE_URL,
        simple_filters_url=f"{settings.API_BASE_URL}/api/v1/simple-filters",
        channel_management_url=f"{settings.API_BASE_URL}/api/v1/static/channel-selection",
        search_settings_url=f"{settings.API_BASE_URL}/api/v1/static/search-settings"
    )
