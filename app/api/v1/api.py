from fastapi import APIRouter

from app.api.v1.endpoints import (
    posts, channels, telegram, real_estate, search_settings, static, ngrok, 
    statistics, simple_filters, user_filter_matches, user_channel_selections, config, price_filters, admin, monitored_channels
)

api_router = APIRouter()
api_router.include_router(
    posts.router, prefix="/posts", tags=["posts"]
)
api_router.include_router(
    channels.router, prefix="/channels", tags=["channels"]
)
api_router.include_router(
    telegram.router, prefix="/telegram", tags=["telegram"]
)
api_router.include_router(
    real_estate.router, prefix="/real-estate", tags=["real-estate"]
)
api_router.include_router(
    search_settings.router, prefix="/search-settings", tags=["search-settings"]
)
api_router.include_router(
    static.router, prefix="/static", tags=["static"]
)
api_router.include_router(
    ngrok.router, prefix="/ngrok", tags=["ngrok"]
)
api_router.include_router(
    statistics.router, prefix="/statistics", tags=["statistics"]
)
api_router.include_router(
    simple_filters.router, prefix="/simple-filters", tags=["simple-filters"]
)
api_router.include_router(
    user_filter_matches.router, prefix="/user-filter-matches", tags=["user-filter-matches"]
)
api_router.include_router(
    user_channel_selections.router, prefix="/user-channel-selections", tags=["user-channel-selections"]
)
api_router.include_router(
    config.router, prefix="/config", tags=["config"]
)
api_router.include_router(
    price_filters.router, prefix="/price-filters", tags=["price-filters"]
)
api_router.include_router(
    admin.router, prefix="/admin", tags=["admin"]
)
api_router.include_router(
    monitored_channels.router, prefix="/monitored-channels", tags=["monitored-channels"]
)