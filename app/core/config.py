from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # === PUBLIC DATA (not secrets) ===
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Telegram Real Estate Bot"

    # === DATABASE SETTINGS (from .env) ===
    MONGODB_URL: str = Field(..., description="MongoDB connection string")
    REDIS_URL: str = Field(..., description="Redis connection string")

    # === APPLICATION SETTINGS ===
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    STARTUP_MESSAGE_LIMIT: int = Field(default=100, description="Number of recent messages to load on startup")

    # === CHANNEL SETTINGS (from .env) ===
    # FORWARDING_CHANNEL removed - we forward directly to bot chat
    TELEGRAM_CHANNEL_USERNAME: str = Field(
        default="rent_comissionfree", description="Username of the monitored channel (without @)"
    )

    # === LLM SETTINGS (from .env) ===
    ENABLE_LLM_PARSING: bool = Field(default=True, description="Enable LLM-based parsing for better accuracy")
    LLM_PROVIDER: str = Field(default="openai", description="LLM provider: openai, anthropic, zai, local, mock")
    LLM_API_KEY: Optional[str] = Field(default=None, description="API key for LLM service")
    LLM_MODEL: str = Field(default="gpt-3.5-turbo", description="LLM model to use for parsing")
    LLM_BASE_URL: Optional[str] = Field(default=None, description="Base URL for LLM API (for local models or Z.AI)")
    LLM_MAX_TOKENS: int = Field(default=1000, description="Maximum tokens for LLM response")
    LLM_TEMPERATURE: float = Field(default=0.1, description="Temperature for LLM generation (0.0-1.0)")

    # === SECRETS (from .env) ===
    TELEGRAM_API_ID: int = Field(..., description="Telegram API ID")
    TELEGRAM_API_HASH: str = Field(..., description="Telegram API Hash")
    TELEGRAM_PHONE: str = Field(..., description="Phone number for Telegram")
    TELEGRAM_SESSION_NAME: str = Field(default="telegram_bot_session")
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(None, description="Bot token")
    TELEGRAM_USER_ID: Optional[int] = Field(None, description="Your Telegram user ID for receiving filtered ads")
    SECRET_KEY: str = Field(..., description="Secret key for JWT tokens")

    # === MONITORED CHANNELS (from .env) ===
    TELEGRAM_MONITORED_CHANNELS: str = Field(
        ..., description="Channels to monitor for real estate ads (comma-separated)"
    )

    # === MONITORED SUBCHANNELS (from .env) ===
    TELEGRAM_MONITORED_SUBCHANNELS: str = Field(
        default="", description="Subchannels (topics) to monitor in format 'channel_id:topic_id' (comma-separated)"
    )

    # === EXCLUDED SUBCHANNELS (from .env) ===
    TELEGRAM_EXCLUDED_SUBCHANNELS: str = Field(
        default="", description="Subchannel IDs to exclude from processing (comma-separated, e.g., '2630,2631')"
    )

    # === WEB APP SETTINGS ===
    API_BASE_URL: str = Field(default="https://your-domain.com", description="Base URL for API (used in Web App)")
    CORS_ORIGINS: str = Field(default="", description="Allowed CORS origins (comma-separated). Empty = no CORS.")

    # === NGROK SETTINGS ===
    NGROK_AUTHTOKEN: Optional[str] = Field(default=None, description="Ngrok auth token for development")

    @property
    def monitored_channels_list(self) -> List[str]:
        """Get all monitored channels as a list"""
        if not self.TELEGRAM_MONITORED_CHANNELS:
            return []

        channels = [channel.strip() for channel in self.TELEGRAM_MONITORED_CHANNELS.split(",") if channel.strip()]

        return channels

    @property
    def monitored_subchannels_list(self) -> List[tuple]:
        """Get all monitored subchannels as a list of (channel_id, topic_id) tuples"""
        if not self.TELEGRAM_MONITORED_SUBCHANNELS:
            return []

        subchannels = []
        for subchannel in self.TELEGRAM_MONITORED_SUBCHANNELS.split(","):
            subchannel = subchannel.strip()
            if not subchannel:
                continue

            if ":" in subchannel:
                try:
                    channel_id, topic_id = subchannel.split(":", 1)
                    subchannels.append((int(channel_id), int(topic_id)))
                except ValueError as e:
                    print(f"Invalid subchannel format: {subchannel} - {e}")
                    continue

        return subchannels

    def get_topic_id_for_channel(self, channel_id: int) -> Optional[int]:
        """Get topic_id for a specific channel from monitored subchannels"""
        for monitored_channel_id, topic_id in self.monitored_subchannels_list:
            if monitored_channel_id == channel_id:
                return topic_id
        return None

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
