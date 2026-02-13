import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote

from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int | None = payload.get("user_id")
        if user_id is None:
            return None
        return payload
    except JWTError:
        return None


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    try:
        parsed = parse_qs(init_data)

        if "hash" not in parsed:
            logger.warning("No hash in init_data")
            return None

        received_hash = parsed.pop("hash")[0]

        # Build data-check-string
        data_check_parts = []
        for key in sorted(parsed.keys()):
            val = parsed[key][0]
            data_check_parts.append(f"{key}={val}")
        data_check_string = "\n".join(data_check_parts)

        # Compute HMAC
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            logger.warning("Invalid init_data hash")
            return None

        # Parse user data
        user_data_str = parsed.get("user", [None])[0]
        if not user_data_str:
            logger.warning("No user data in init_data")
            return None

        user_data = json.loads(unquote(user_data_str))
        return user_data

    except Exception as e:
        logger.error("Error validating Telegram init data: %s", e)
        return None
