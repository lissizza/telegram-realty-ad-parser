"""
Service for sending notifications to administrators
"""

import logging
from typing import Optional
from datetime import datetime, timezone, timedelta

from app.db.mongodb import mongodb
from app.models.admin import UserRole

logger = logging.getLogger(__name__)


class AdminNotificationService:
    """Service for notifying administrators about critical events"""
    
    def __init__(self):
        self.notification_service = None
        self._last_quota_notification = None  # Timestamp of last quota notification
        self._quota_notification_interval = 900  # Notify at most once per 15 minutes (900 seconds)
        self._last_restart_notification = None  # Timestamp of last restart notification
        self._restart_notification_interval = 900  # Notify at most once per 15 minutes (900 seconds)
    
    def set_notification_service(self, notification_service):
        """Set the notification service (injected from main)"""
        self.notification_service = notification_service
    
    async def notify_quota_exceeded(self, error_message: str) -> None:
        """Notify super admins about LLM quota exceeded"""
        try:
            logger.info("notify_quota_exceeded called with error: %s", error_message[:100])
            
            # Check if we've notified recently (within interval)
            now = datetime.now(timezone.utc)
            if self._last_quota_notification:
                time_since_last = (now - self._last_quota_notification).total_seconds()
                if time_since_last < self._quota_notification_interval:
                    logger.info("Quota error already notified %d seconds ago, skipping (interval: %d)", 
                               time_since_last, self._quota_notification_interval)
                    return
                else:
                    logger.info("Last quota notification was %d seconds ago, sending new notification", time_since_last)
            else:
                logger.info("First quota notification, proceeding to send")
            
            db = mongodb.get_database()
            
            # Find all super admins
            super_admins = await db.admin_users.find({
                'role': UserRole.SUPER_ADMIN.value,
                'is_active': True
            }).to_list(length=None)
            
            if not super_admins:
                logger.warning("No super admins found to notify about quota error")
                return
            
            # Create notification message
            message = f"""
🚨 *Исчерпан лимит OpenAI API\\!*

Новые сообщения НЕ парсятся

⏰ *Время:* {datetime.now(timezone.utc).strftime('%Y\\-%m\\-%d %H:%M:%S UTC')}

Проверьте баланс на platform\\.openai\\.com и пополните счет.
"""
            
            # Send to all super admins
            if self.notification_service:
                logger.info("Sending quota notification to %d super admins", len(super_admins))
                sent_count = 0
                for admin in super_admins:
                    user_id = admin.get('user_id')
                    if user_id:
                        try:
                            logger.info("Attempting to send notification to admin %s", user_id)
                            await self.notification_service.send_message(
                                user_id=user_id,
                                message=message,
                                parse_mode="MarkdownV2"
                            )
                            logger.info("✅ Successfully sent quota error notification to super admin %s", user_id)
                            sent_count += 1
                        except Exception as e:
                            logger.error("❌ Error sending notification to admin %s: %s", user_id, e)
                
                # Mark notification time (even if some failed)
                self._last_quota_notification = now
                logger.info("Quota notification process completed: sent to %d/%d admins at %s, next allowed after %s", 
                           sent_count, len(super_admins), now, now + timedelta(seconds=self._quota_notification_interval))
            else:
                logger.error("Notification service not available - cannot send quota notifications!")
                # Still mark as notified to avoid infinite retry without notification service
                self._last_quota_notification = now
                
        except Exception as e:
            logger.error("Error notifying admins about quota: %s", e)
    
    def _escape_markdown(self, text: str) -> str:
        """Escape special characters for MarkdownV2"""
        if not text:
            return ""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    async def notify_service_restart(self, attempt: int, error: str, will_retry: bool) -> None:
        """Notify super admins about service restart attempts"""
        try:
            logger.info("notify_service_restart called: attempt=%d, will_retry=%s, error=%s", 
                       attempt, will_retry, error[:100])
            
            # Check if we've notified recently (within interval)
            now = datetime.now(timezone.utc)
            if self._last_restart_notification:
                time_since_last = (now - self._last_restart_notification).total_seconds()
                if time_since_last < self._restart_notification_interval:
                    logger.info("Service restart already notified %d seconds ago, skipping (interval: %d)", 
                               time_since_last, self._restart_notification_interval)
                    return
                else:
                    logger.info("Last restart notification was %d seconds ago, sending new notification", time_since_last)
            else:
                logger.info("First restart notification, proceeding to send")
            
            db = mongodb.get_database()
            
            # Find all super admins
            super_admins = await db.admin_users.find({
                'role': UserRole.SUPER_ADMIN.value,
                'is_active': True
            }).to_list(length=None)
            
            if not super_admins:
                logger.warning("No super admins found to notify about service restart")
                return
            
            # Create notification message
            status_emoji = "🔄" if will_retry else "❌"
            status_text = "будет повторная попытка" if will_retry else "превышено максимальное количество попыток"
            
            message = f"""
{status_emoji} *Проблема с подключением Telegram\\!*

Попытка переподключения: {attempt}/3
Статус: {status_text}

⏰ *Время:* {datetime.now(timezone.utc).strftime('%Y\\-%m\\-%d %H:%M:%S UTC')}

Ошибка: `{self._escape_markdown(error)}`

{'Сервис будет автоматически перезапущен через несколько секунд\\.' if will_retry else 'Требуется ручное вмешательство\\!'}
"""
            
            # Send to all super admins
            if self.notification_service:
                logger.info("Sending restart notification to %d super admins", len(super_admins))
                sent_count = 0
                for admin in super_admins:
                    user_id = admin.get('user_id')
                    if user_id:
                        try:
                            logger.info("Attempting to send restart notification to admin %s", user_id)
                            await self.notification_service.send_message(
                                user_id=user_id,
                                message=message,
                                parse_mode="MarkdownV2"
                            )
                            logger.info("✅ Successfully sent restart notification to super admin %s", user_id)
                            sent_count += 1
                        except Exception as e:
                            logger.error("❌ Error sending restart notification to admin %s: %s", user_id, e)
                
                # Mark notification time (even if some failed)
                self._last_restart_notification = now
                logger.info("Restart notification process completed: sent to %d/%d admins at %s, next allowed after %s", 
                           sent_count, len(super_admins), now, now + timedelta(seconds=self._restart_notification_interval))
            else:
                logger.error("Notification service not available - cannot send restart notifications!")
                # Still mark as notified to avoid infinite retry without notification service
                self._last_restart_notification = now
                
        except Exception as e:
            logger.error("Error notifying admins about service restart: %s", e)

    def reset_quota_notification(self) -> None:
        """Reset quota notification timestamp (call after quota is restored)"""
        self._last_quota_notification = None
        logger.info("Quota notification timestamp reset")

    def reset_restart_notification(self) -> None:
        """Reset restart notification timestamp (call after service is healthy)"""
        self._last_restart_notification = None
        logger.info("Restart notification timestamp reset")


# Global instance
admin_notification_service = AdminNotificationService()
