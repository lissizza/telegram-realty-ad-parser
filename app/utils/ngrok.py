"""
Simple ngrok utilities for getting tunnel information
"""

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


async def get_ngrok_url() -> Optional[str]:
    """Get the current ngrok tunnel URL"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:4040/api/tunnels")
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get("tunnels", [])

                # Find HTTPS tunnel first
                for tunnel in tunnels:
                    if tunnel.get("proto") == "https" and tunnel.get("public_url"):
                        return str(tunnel["public_url"])

                # Fallback to HTTP tunnel
                for tunnel in tunnels:
                    if tunnel.get("proto") == "http" and tunnel.get("public_url"):
                        return str(tunnel["public_url"])

        return None
    except Exception as e:
        logger.error("Error getting ngrok URL: %s", e)
        return None


async def is_ngrok_running() -> bool:
    """Check if ngrok is running"""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get("http://localhost:4040/api/tunnels")
            return response.status_code == 200
    except Exception:
        return False


async def get_ngrok_info() -> Dict[str, Any]:
    """Get detailed ngrok information"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:4040/api/tunnels")
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get("tunnels", [])

                result: Dict[str, Any] = {
                    "status": "running" if tunnels else "not_running",
                    "tunnels": [],
                    "web_interface_url": "http://localhost:4040",
                }

                for tunnel in tunnels:
                    tunnel_info: Dict[str, Any] = {
                        "name": tunnel.get("name", "unnamed"),
                        "proto": tunnel.get("proto"),
                        "public_url": tunnel.get("public_url"),
                        "config": tunnel.get("config", {}),
                        "metrics": tunnel.get("metrics", {}),
                    }
                    result["tunnels"].append(tunnel_info)

                return result
            return {"status": "error", "message": f"HTTP {response.status_code}"}

    except Exception as e:
        logger.error("Error getting ngrok info: %s", e)
        return {"status": "error", "message": str(e)}


async def get_web_app_url() -> Optional[str]:
    """Get the Web App URL for Telegram"""
    tunnel_url = await get_ngrok_url()
    if tunnel_url:
        return f"{tunnel_url}/api/v1/static/search-settings"
    return None
















