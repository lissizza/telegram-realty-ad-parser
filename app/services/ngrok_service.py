import logging
import requests
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

class NgrokService:
    """Service for managing ngrok tunnels"""
    
    def __init__(self):
        self.ngrok_api_url = "http://localhost:4040/api"
        self.auth_token = getattr(settings, 'NGROK_AUTHTOKEN', None)
    
    async def get_tunnel_url(self) -> Optional[str]:
        """Get the current ngrok tunnel URL"""
        try:
            response = requests.get(f"{self.ngrok_api_url}/tunnels", timeout=5)
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get('tunnels', [])
                
                # Find the first HTTP tunnel
                for tunnel in tunnels:
                    if tunnel.get('proto') == 'https' and tunnel.get('public_url'):
                        return tunnel['public_url']
                
                # Fallback to HTTP tunnel
                for tunnel in tunnels:
                    if tunnel.get('proto') == 'http' and tunnel.get('public_url'):
                        return tunnel['public_url']
                        
            return None
        except Exception as e:
            logger.error(f"Error getting ngrok URL: {e}")
            return None
    
    async def get_tunnel_info(self) -> Dict[str, Any]:
        """Get detailed tunnel information"""
        try:
            response = requests.get(f"{self.ngrok_api_url}/tunnels", timeout=5)
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get('tunnels', [])
                
                result = {
                    "status": "running" if tunnels else "not_running",
                    "tunnels": [],
                    "web_interface_url": f"{self.ngrok_api_url.replace('/api', '')}"
                }
                
                for tunnel in tunnels:
                    tunnel_info = {
                        "name": tunnel.get('name', 'unnamed'),
                        "proto": tunnel.get('proto'),
                        "public_url": tunnel.get('public_url'),
                        "config": tunnel.get('config', {}),
                        "metrics": tunnel.get('metrics', {})
                    }
                    result["tunnels"].append(tunnel_info)
                
                return result
            else:
                return {"status": "error", "message": f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error getting tunnel info: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_web_app_url(self) -> Optional[str]:
        """Get the Web App URL for Telegram"""
        tunnel_url = await self.get_tunnel_url()
        if tunnel_url:
            return f"{tunnel_url}/api/v1/static/search-settings"
        return None
    
    async def get_api_base_url(self) -> Optional[str]:
        """Get the API base URL"""
        return await self.get_tunnel_url()
    
    async def is_ngrok_running(self) -> bool:
        """Check if ngrok is running"""
        try:
            response = requests.get(f"{self.ngrok_api_url}/tunnels", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    async def set_manual_url(self, url: str) -> Dict[str, Any]:
        """Set a manual ngrok URL (for when ngrok is running externally)"""
        try:
            # Validate URL format
            if not url.startswith(('http://', 'https://')):
                url = f"https://{url}"
            
            # Test if URL is accessible
            response = requests.get(f"{url}/api/v1/ngrok/status", timeout=10)
            if response.status_code == 200:
                return {
                    "status": "success",
                    "message": "Manual ngrok URL set successfully",
                    "url": url,
                    "web_app_url": f"{url}/api/v1/static/search-settings"
                }
            else:
                return {
                    "status": "error",
                    "message": f"URL is not accessible: HTTP {response.status_code}",
                    "url": url
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error setting manual URL: {str(e)}",
                "url": url
            }

# Global instance
ngrok_service = NgrokService()



