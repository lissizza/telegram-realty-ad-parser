"""
Admin models for Telegram Bot Admin system
"""

from datetime import datetime, UTC
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """User roles in the system"""
    USER = "user"                    # Regular user - can only manage own filters
    MODERATOR = "moderator"          # Can manage channels
    ADMIN = "admin"                  # Full access except admin management
    SUPER_ADMIN = "super_admin"      # Can manage other admins


class AdminPermission(str, Enum):
    """Admin permissions"""
    MANAGE_CHANNELS = "manage_channels"      # Add/edit/delete channels
    MANAGE_USERS = "manage_users"            # Ban/unban users, assign roles
    VIEW_STATS = "view_stats"                # View system statistics
    VIEW_LOGS = "view_logs"                  # View system logs
    MANAGE_ADMINS = "manage_admins"          # Manage admin users
    MANAGE_SETTINGS = "manage_settings"      # Manage bot settings


class AdminUser(BaseModel):
    """Admin user model"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: UserRole = UserRole.USER
    permissions: List[AdminPermission] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: Optional[int] = None  # Who created this admin
    last_activity: Optional[datetime] = None


class AdminAction(BaseModel):
    """Admin action log model"""
    id: Optional[str] = None
    admin_user_id: int
    action: str  # e.g., "channel_added", "user_banned"
    target_type: str  # e.g., "channel", "user"
    target_id: str  # ID of the target (channel_id, user_id)
    details: dict = Field(default_factory=dict)  # Additional action details
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AdminStats(BaseModel):
    """Admin statistics model"""
    total_users: int
    active_users: int
    total_channels: int
    active_channels: int
    total_filters: int
    total_messages_processed: int
    messages_today: int
    system_uptime: str
    last_activity: Optional[datetime] = None


# Role-based permissions mapping
ROLE_PERMISSIONS = {
    UserRole.USER: [],
    UserRole.MODERATOR: [
        AdminPermission.MANAGE_CHANNELS,
        AdminPermission.VIEW_STATS,
    ],
    UserRole.ADMIN: [
        AdminPermission.MANAGE_CHANNELS,
        AdminPermission.MANAGE_USERS,
        AdminPermission.VIEW_STATS,
        AdminPermission.VIEW_LOGS,
    ],
    UserRole.SUPER_ADMIN: [
        AdminPermission.MANAGE_CHANNELS,
        AdminPermission.MANAGE_USERS,
        AdminPermission.VIEW_STATS,
        AdminPermission.VIEW_LOGS,
        AdminPermission.MANAGE_ADMINS,
        AdminPermission.MANAGE_SETTINGS,
    ],
}




