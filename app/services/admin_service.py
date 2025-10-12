"""
Admin service for managing admin users and permissions
"""

import logging
from datetime import datetime, UTC
from typing import List, Optional, Dict, Any

from app.db.mongodb import mongodb
from app.models.admin import AdminUser, AdminAction, AdminStats, UserRole, AdminPermission, ROLE_PERMISSIONS

logger = logging.getLogger(__name__)


class AdminService:
    """Service for managing admin users and permissions"""
    
    async def get_admin_user(self, user_id: int) -> Optional[AdminUser]:
        """Get admin user by user_id"""
        try:
            db = mongodb.get_database()
            doc = await db.admin_users.find_one({"user_id": user_id})
            
            if not doc:
                return None
                
            doc["id"] = str(doc["_id"])
            doc.pop("_id", None)
            return AdminUser(**doc)
            
        except Exception as e:
            logger.error("Error getting admin user %s: %s", user_id, e)
            return None
    
    async def create_admin_user(
        self, 
        user_id: int, 
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: UserRole = UserRole.USER,
        created_by: Optional[int] = None
    ) -> bool:
        """Create new admin user"""
        try:
            db = mongodb.get_database()
            
            # Check if user already exists
            existing = await self.get_admin_user(user_id)
            if existing:
                logger.warning("Admin user %s already exists", user_id)
                return False
            
            # Get permissions for the role
            permissions = ROLE_PERMISSIONS.get(role, [])
            
            admin_user = AdminUser(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                role=role,
                permissions=permissions,
                created_by=created_by
            )
            
            # Convert to dict and save
            admin_dict = admin_user.model_dump()
            admin_dict["created_at"] = datetime.now(UTC)
            admin_dict["updated_at"] = datetime.now(UTC)
            
            result = await db.admin_users.insert_one(admin_dict)
            
            if result.inserted_id:
                logger.info("Created admin user %s with role %s", user_id, role)
                return True
            else:
                logger.error("Failed to create admin user %s", user_id)
                return False
                
        except Exception as e:
            logger.error("Error creating admin user %s: %s", user_id, e)
            return False
    
    async def update_admin_user(self, user_id: int, **updates) -> bool:
        """Update admin user"""
        try:
            db = mongodb.get_database()
            
            # Update permissions if role changed
            if "role" in updates:
                new_role = updates["role"]
                updates["permissions"] = ROLE_PERMISSIONS.get(new_role, [])
            
            updates["updated_at"] = datetime.now(UTC)
            
            result = await db.admin_users.update_one(
                {"user_id": user_id},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                logger.info("Updated admin user %s", user_id)
                return True
            else:
                logger.warning("No changes made to admin user %s", user_id)
                return False
                
        except Exception as e:
            logger.error("Error updating admin user %s: %s", user_id, e)
            return False
    
    async def delete_admin_user(self, user_id: int) -> bool:
        """Delete admin user (soft delete)"""
        try:
            return await self.update_admin_user(user_id, is_active=False)
        except Exception as e:
            logger.error("Error deleting admin user %s: %s", user_id, e)
            return False
    
    async def check_admin_permission(self, user_id: int, permission: AdminPermission) -> bool:
        """Check if user has specific admin permission"""
        try:
            admin_user = await self.get_admin_user(user_id)
            
            if not admin_user or not admin_user.is_active:
                return False
            
            # Super admin has all permissions
            if admin_user.role == UserRole.SUPER_ADMIN:
                return True
            
            # Check if permission is in user's permissions
            return permission in admin_user.permissions
            
        except Exception as e:
            logger.error("Error checking admin permission for user %s: %s", user_id, e)
            return False
    
    async def is_admin(self, user_id: int) -> bool:
        """Check if user is any kind of admin"""
        try:
            admin_user = await self.get_admin_user(user_id)
            return admin_user is not None and admin_user.is_active and admin_user.role != UserRole.USER
        except Exception as e:
            logger.error("Error checking if user %s is admin: %s", user_id, e)
            return False
    
    async def get_all_admin_users(self) -> List[AdminUser]:
        """Get all admin users"""
        try:
            db = mongodb.get_database()
            admin_users = []
            
            async for doc in db.admin_users.find({"is_active": True}):
                doc["id"] = str(doc["_id"])
                doc.pop("_id", None)
                admin_users.append(AdminUser(**doc))
            
            return admin_users
            
        except Exception as e:
            logger.error("Error getting all admin users: %s", e)
            return []
    
    async def log_admin_action(
        self,
        admin_user_id: int,
        action: str,
        target_type: str,
        target_id: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Log admin action"""
        try:
            db = mongodb.get_database()
            
            admin_action = AdminAction(
                admin_user_id=admin_user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details or {}
            )
            
            action_dict = admin_action.model_dump()
            action_dict["timestamp"] = datetime.now(UTC)
            
            await db.admin_actions.insert_one(action_dict)
            
            logger.info("Logged admin action: %s by user %s", action, admin_user_id)
            return True
            
        except Exception as e:
            logger.error("Error logging admin action: %s", e)
            return False
    
    async def get_admin_stats(self) -> AdminStats:
        """Get admin statistics"""
        try:
            db = mongodb.get_database()
            
            # Count users
            total_users = await db.admin_users.count_documents({})
            active_users = await db.admin_users.count_documents({"is_active": True})
            
            # Count channels
            total_channels = await db.user_channel_subscriptions.count_documents({})
            active_channels = await db.user_channel_subscriptions.count_documents({"is_active": True})
            
            # Count filters
            total_filters = await db.simple_filters.count_documents({})
            
            # Count messages
            total_messages = await db.incoming_messages.count_documents({})
            
            # Messages today
            today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            messages_today = await db.incoming_messages.count_documents({
                "created_at": {"$gte": today}
            })
            
            # Get last activity
            last_activity_doc = await db.admin_actions.find_one(
                {},
                sort=[("timestamp", -1)]
            )
            last_activity = last_activity_doc.get("timestamp") if last_activity_doc else None
            
            return AdminStats(
                total_users=total_users,
                active_users=active_users,
                total_channels=total_channels,
                active_channels=active_channels,
                total_filters=total_filters,
                total_messages_processed=total_messages,
                messages_today=messages_today,
                system_uptime="Unknown",  # TODO: Implement uptime tracking
                last_activity=last_activity
            )
            
        except Exception as e:
            logger.error("Error getting admin stats: %s", e)
            return AdminStats(
                total_users=0,
                active_users=0,
                total_channels=0,
                active_channels=0,
                total_filters=0,
                total_messages_processed=0,
                messages_today=0,
                system_uptime="Error",
                last_activity=None
            )
    
    async def get_recent_admin_actions(self, limit: int = 50) -> List[AdminAction]:
        """Get recent admin actions"""
        try:
            db = mongodb.get_database()
            actions = []
            
            async for doc in db.admin_actions.find().sort("timestamp", -1).limit(limit):
                doc["id"] = str(doc["_id"])
                doc.pop("_id", None)
                actions.append(AdminAction(**doc))
            
            return actions
            
        except Exception as e:
            logger.error("Error getting recent admin actions: %s", e)
            return []




