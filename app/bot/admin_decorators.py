"""
Admin decorators and middleware for Telegram Bot
"""

import logging
from functools import wraps
from typing import Callable, Any

from telegram import Update
from telegram.ext import ContextTypes

from app.services.admin_service import AdminService
from app.models.admin import AdminPermission

logger = logging.getLogger(__name__)

# Global admin service instance
admin_service = AdminService()


def require_admin(permission: AdminPermission = None):
    """
    Decorator to require admin permissions for bot commands
    
    Args:
        permission: Specific permission required (None for any admin role)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
            user_id = update.effective_user.id
            
            try:
                # Check if user is admin
                if not await admin_service.is_admin(user_id):
                    await update.message.reply_text(
                        "❌ У вас нет прав администратора для выполнения этой команды"
                    )
                    return
                
                # Check specific permission if required
                if permission and not await admin_service.check_admin_permission(user_id, permission):
                    await update.message.reply_text(
                        f"❌ У вас нет прав для выполнения этой операции. "
                        f"Требуется разрешение: {permission.value}"
                    )
                    return
                
                # Log admin action
                await admin_service.log_admin_action(
                    admin_user_id=user_id,
                    action="command_executed",
                    target_type="command",
                    target_id=func.__name__,
                    details={"command": func.__name__, "permission": permission.value if permission else None}
                )
                
                # Execute the function
                return await func(update, context)
                
            except Exception as e:
                logger.error("Error in admin decorator for user %s: %s", user_id, e)
                await update.message.reply_text(
                    "❌ Произошла ошибка при проверке прав доступа"
                )
                return
                
        return wrapper
    return decorator


def require_super_admin(func: Callable) -> Callable:
    """Decorator to require super admin role"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        user_id = update.effective_user.id
        
        try:
            admin_user = await admin_service.get_admin_user(user_id)
            
            if not admin_user or admin_user.role.value != "super_admin":
                await update.message.reply_text(
                    "❌ Эта команда доступна только супер-администраторам"
                )
                return
            
            return await func(update, context)
            
        except Exception as e:
            logger.error("Error in super admin decorator for user %s: %s", user_id, e)
            await update.message.reply_text(
                "❌ Произошла ошибка при проверке прав доступа"
            )
            return
            
    return wrapper


def log_admin_action(action: str, target_type: str = "command"):
    """
    Decorator to log admin actions
    
    Args:
        action: Action being performed
        target_type: Type of target (command, user, channel, etc.)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
            user_id = update.effective_user.id
            
            try:
                # Execute the function first
                result = await func(update, context)
                
                # Log the action
                await admin_service.log_admin_action(
                    admin_user_id=user_id,
                    action=action,
                    target_type=target_type,
                    target_id=func.__name__,
                    details={"command": func.__name__}
                )
                
                return result
                
            except Exception as e:
                logger.error("Error in admin action logger for user %s: %s", user_id, e)
                # Still execute the function even if logging fails
                return await func(update, context)
                
        return wrapper
    return decorator


async def check_admin_permission(user_id: int, permission: AdminPermission) -> bool:
    """Check if user has specific admin permission"""
    try:
        return await admin_service.check_admin_permission(user_id, permission)
    except Exception as e:
        logger.error("Error checking admin permission for user %s: %s", user_id, e)
        return False


async def is_admin(user_id: int) -> bool:
    """Check if user is any kind of admin"""
    try:
        return await admin_service.is_admin(user_id)
    except Exception as e:
        logger.error("Error checking if user %s is admin: %s", user_id, e)
        return False


async def is_super_admin(user_id: int) -> bool:
    """Check if user is super admin"""
    try:
        admin_user = await admin_service.get_admin_user(user_id)
        return admin_user is not None and admin_user.role.value == "super_admin"
    except Exception as e:
        logger.error("Error checking if user %s is super admin: %s", user_id, e)
        return False




