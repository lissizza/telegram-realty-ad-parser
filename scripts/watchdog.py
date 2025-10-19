#!/usr/bin/env python3
"""
Watchdog script for monitoring application health and triggering restarts
Can be run as standalone script or as a separate container
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import docker
from docker.errors import DockerException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/watchdog.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class WatchdogService:
    """Service for monitoring application health and triggering restarts"""
    
    def __init__(self, 
                 health_url: str = "http://localhost:8001/health",
                 check_interval: int = 30,
                 max_failures: int = 3,
                 restart_command: str = "docker-compose restart app"):
        self.health_url = health_url
        self.check_interval = check_interval
        self.max_failures = max_failures
        self.restart_command = restart_command
        self.consecutive_failures = 0
        self.last_check_time: Optional[datetime] = None
        self.docker_client: Optional[docker.DockerClient] = None
        
        # Initialize Docker client if available
        try:
            self.docker_client = docker.from_env()
            logger.info("Docker client initialized successfully")
        except DockerException as e:
            logger.warning("Docker client not available: %s", e)
            self.docker_client = None
    
    async def check_health(self) -> bool:
        """Check application health via HTTP endpoint"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.health_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        is_healthy = data.get("status") == "healthy"
                        logger.info("Health check passed: %s", data.get("status"))
                        return is_healthy
                    else:
                        logger.warning("Health check failed with status %d", response.status)
                        return False
        except Exception as e:
            logger.error("Health check error: %s", e)
            return False
    
    async def restart_application(self) -> bool:
        """Restart the application using Docker or system command"""
        try:
            if self.docker_client:
                # Use Docker client to restart container
                container = self.docker_client.containers.get("rent-no-fees-app-1")
                container.restart()
                logger.info("Application restarted via Docker client")
                return True
            else:
                # Use system command
                import subprocess
                result = subprocess.run(
                    self.restart_command.split(),
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    logger.info("Application restarted via system command")
                    return True
                else:
                    logger.error("Restart command failed: %s", result.stderr)
                    return False
        except Exception as e:
            logger.error("Error restarting application: %s", e)
            return False
    
    async def run(self):
        """Main watchdog loop"""
        logger.info("Starting watchdog service")
        logger.info("Health URL: %s", self.health_url)
        logger.info("Check interval: %d seconds", self.check_interval)
        logger.info("Max failures before restart: %d", self.max_failures)
        
        while True:
            try:
                self.last_check_time = datetime.now(timezone.utc)
                is_healthy = await self.check_health()
                
                if is_healthy:
                    if self.consecutive_failures > 0:
                        logger.info("Application is healthy again, resetting failure counter")
                    self.consecutive_failures = 0
                else:
                    self.consecutive_failures += 1
                    logger.warning("Health check failed (%d/%d consecutive failures)", 
                                 self.consecutive_failures, self.max_failures)
                    
                    if self.consecutive_failures >= self.max_failures:
                        logger.error("Max failures reached, attempting to restart application")
                        restart_success = await self.restart_application()
                        
                        if restart_success:
                            logger.info("Application restart initiated, resetting failure counter")
                            self.consecutive_failures = 0
                            # Wait longer after restart
                            await asyncio.sleep(60)
                        else:
                            logger.error("Failed to restart application")
                            # Wait before trying again
                            await asyncio.sleep(300)  # 5 minutes
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Watchdog stopped by user")
                break
            except Exception as e:
                logger.error("Unexpected error in watchdog loop: %s", e)
                await asyncio.sleep(30)  # Wait before retrying


async def main():
    """Main function"""
    # Get configuration from environment variables
    health_url = os.getenv("WATCHDOG_HEALTH_URL", "http://localhost:8001/health")
    check_interval = int(os.getenv("WATCHDOG_CHECK_INTERVAL", "30"))
    max_failures = int(os.getenv("WATCHDOG_MAX_FAILURES", "3"))
    restart_command = os.getenv("WATCHDOG_RESTART_COMMAND", "docker-compose restart app")
    
    # Create and run watchdog
    watchdog = WatchdogService(
        health_url=health_url,
        check_interval=check_interval,
        max_failures=max_failures,
        restart_command=restart_command
    )
    
    await watchdog.run()


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs("/app/logs", exist_ok=True)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Watchdog stopped")
    except Exception as e:
        logger.error("Fatal error in watchdog: %s", e)
        sys.exit(1)
