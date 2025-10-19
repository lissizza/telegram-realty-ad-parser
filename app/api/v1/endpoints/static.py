from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path

from app.bot.admin_decorators import is_admin

router = APIRouter()

# Get the static files directory
STATIC_DIR = Path(__file__).parent.parent.parent.parent / "static"

@router.get("/search-settings")
async def get_search_settings_page():
    """Serve the search settings HTML page"""
    return FileResponse(STATIC_DIR / "search_settings.html")

@router.get("/channel-management")
async def get_channel_management_page():
    """Serve the channel management HTML page"""
    return FileResponse(STATIC_DIR / "channel_management.html")

@router.get("/simple-filters")
async def get_simple_filters_page():
    """Serve the simple filters HTML page"""
    return FileResponse(STATIC_DIR / "simple_filters.html")


@router.get("/channel-selection")
async def get_channel_selection_page():
    """Serve the channel selection HTML page"""
    return FileResponse(STATIC_DIR / "channel_selection.html")

@router.get("/")
async def get_static_files():
    """List available static files"""
    files = []
    if STATIC_DIR.exists():
        for file_path in STATIC_DIR.iterdir():
            if file_path.is_file():
                files.append({
                    "name": file_path.name,
                    "path": f"/static/{file_path.name}",
                    "size": file_path.stat().st_size
                })
    return {"files": files}
