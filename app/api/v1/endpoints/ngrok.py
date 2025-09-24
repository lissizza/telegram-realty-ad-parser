from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel
from app.services.ngrok_service import ngrok_service

router = APIRouter()

class NgrokUrlUpdate(BaseModel):
    ngrok_url: str

@router.get("/status")
async def get_ngrok_status() -> Dict[str, Any]:
    """Get ngrok tunnel status and information"""
    try:
        info = await ngrok_service.get_tunnel_info()
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting ngrok status: {str(e)}")

@router.get("/url")
async def get_ngrok_url() -> Dict[str, str]:
    """Get the current ngrok tunnel URL"""
    try:
        tunnel_url = await ngrok_service.get_tunnel_url()
        if not tunnel_url:
            raise HTTPException(status_code=404, detail="No ngrok tunnel found. Make sure ngrok is running.")
        
        web_app_url = await ngrok_service.get_web_app_url()
        
        return {
            "tunnel_url": tunnel_url,
            "api_base_url": tunnel_url,
            "web_app_url": web_app_url,
            "message": "Use the web_app_url in @BotFather to configure your Web App"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting ngrok URL: {str(e)}")

@router.get("/webapp-url")
async def get_webapp_url() -> Dict[str, str]:
    """Get the Web App URL for Telegram configuration"""
    try:
        web_app_url = await ngrok_service.get_web_app_url()
        if not web_app_url:
            raise HTTPException(status_code=404, detail="No ngrok tunnel found. Make sure ngrok is running.")
        
        return {
            "web_app_url": web_app_url,
            "instructions": [
                "1. Copy the web_app_url above",
                "2. Open @BotFather in Telegram",
                "3. Send /newapp command",
                "4. Select your bot",
                "5. Paste the web_app_url as the URL",
                "6. Configure other settings and save"
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting Web App URL: {str(e)}")

@router.get("/config")
async def get_ngrok_config() -> Dict[str, Any]:
    """Get ngrok configuration for development"""
    try:
        is_running = await ngrok_service.is_ngrok_running()
        if not is_running:
            return {
                "status": "ngrok_not_running",
                "message": "Ngrok is not running. Start it with: ngrok http 8000",
                "commands": [
                    "ngrok http 8000",
                    "ngrok http 8000 --subdomain=your-app-name"
                ]
            }
        
        tunnel_url = await ngrok_service.get_tunnel_url()
        web_app_url = await ngrok_service.get_web_app_url()
        
        return {
            "status": "running",
            "tunnel_url": tunnel_url,
            "web_app_url": web_app_url,
            "env_update": {
                "API_BASE_URL": tunnel_url,
                "WEB_APP_URL": web_app_url
            },
            "next_steps": [
                "1. Update your .env file with the API_BASE_URL above",
                "2. Restart your application",
                "3. Use the web_app_url in @BotFather",
                "4. Test the Web App in Telegram"
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting ngrok config: {str(e)}")

@router.post("/start")
async def start_ngrok_tunnel() -> Dict[str, str]:
    """Instructions to start ngrok tunnel"""
    return {
        "message": "To start ngrok tunnel, run one of these commands:",
        "commands": [
            "ngrok http 8000",
            "ngrok http 8000 --subdomain=your-app-name",
            "ngrok http 8000 --region=us"
        ],
        "note": "Make sure your application is running on port 8000 first"
    }

@router.post("/update")
async def update_ngrok_url(request: NgrokUrlUpdate) -> Dict[str, Any]:
    """Update ngrok URL manually"""
    try:
        result = await ngrok_service.set_manual_url(request.ngrok_url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating ngrok URL: {str(e)}")



