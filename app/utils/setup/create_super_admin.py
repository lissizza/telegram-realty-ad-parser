#!/usr/bin/env python3
"""
Script to create the first super admin user
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, '/app')

from app.db.mongodb import mongodb
from app.services.admin_service import AdminService
from app.services.telegram_user_service import TelegramUserService
from app.models.admin import UserRole
from app.services import get_telegram_service

async def create_super_admin():
    """Create the first super admin user"""
    try:
        # Connect to database
        await mongodb.connect_to_mongo()
        print("✅ Connected to database")
        
        # Initialize services
        admin_service = AdminService()
        
        # Get existing Telegram service (singleton)
        telegram_service = get_telegram_service()
        if not telegram_service or not telegram_service.client:
            print("❌ Telegram service not available. Make sure the bot is running.")
            return
        
        print("✅ Using existing Telegram service")
        
        # Initialize telegram user service with existing client
        telegram_user_service = TelegramUserService(client=telegram_service.client)
        
        # Get user identifier from command line or prompt
        if len(sys.argv) > 1:
            user_identifier = sys.argv[1]
        else:
            user_identifier = input("Enter Telegram user ID or username for super admin: ")
        
        # Resolve user information
        print(f"Resolving user information for: {user_identifier}")
        user_info = await telegram_user_service.resolve_user_identifier(user_identifier)
        
        if not user_info:
            print(f"❌ User not found: {user_identifier}")
            return
        
        user_id = user_info["id"]
        username = user_info["username"]
        first_name = user_info["first_name"]
        last_name = user_info["last_name"]
        
        print(f"✅ Found user: {first_name} {last_name} (@{username}) - ID: {user_id}")
        
        # Create super admin
        success = await admin_service.create_admin_user(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.SUPER_ADMIN,
            created_by=None  # First admin, no creator
        )
        
        if success:
            print(f"✅ Super admin created successfully for user ID: {user_id}")
            print("🔑 This user now has full admin access to the bot")
        else:
            print(f"❌ Failed to create super admin for user ID: {user_id}")
            
    except Exception as e:
        print(f"❌ Error creating super admin: {e}")
    finally:
        # Close database connection (Telegram service stays connected)
        await mongodb.close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(create_super_admin())
