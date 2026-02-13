import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.bot.admin_decorators import is_admin
from app.core.config import settings
from app.core.security import create_access_token, validate_telegram_init_data
from app.models.token import TokenResponse
from app.services.user_service import user_service

router = APIRouter()
logger = logging.getLogger(__name__)


class AuthRequest(BaseModel):
    init_data: str


@router.post("/token", response_model=TokenResponse)
async def authenticate(request: AuthRequest):
    """Authenticate via Telegram WebApp initData and return JWT token"""
    bot_token = settings.TELEGRAM_BOT_TOKEN
    if not bot_token:
        raise HTTPException(status_code=500, detail="Bot token not configured")

    user_data = validate_telegram_init_data(request.init_data, bot_token)
    if user_data is None:
        raise HTTPException(status_code=401, detail="Invalid Telegram init data")

    user_id = user_data.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="No user ID in init data")

    # Auto-authorize the user
    username = user_data.get("username")
    first_name = user_data.get("first_name")
    await user_service.add_authorized_user(user_id, username, first_name)

    # Create JWT
    access_token = create_access_token({"user_id": user_id})

    # Check admin status
    admin_status = await is_admin(user_id)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user_id,
        is_admin=admin_status,
    )
