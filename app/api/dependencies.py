from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.bot.admin_decorators import is_admin, is_super_admin
from app.core.security import verify_access_token
from app.models.token import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> TokenData:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenData(user_id=payload["user_id"])


async def get_current_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if not await is_admin(current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def get_current_super_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if not await is_super_admin(current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return current_user
