"""
Admin commands for Telegram Bot
"""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.bot.admin_decorators import require_admin, require_super_admin, log_admin_action
from app.models.admin import AdminPermission, UserRole
from app.services.admin_service import AdminService
from app.services.filter_service import FilterService
from app.services.user_channel_selection_service import UserChannelSelectionService
from app.services.telegram_user_service import TelegramUserService
from app.services.monitored_channel_service import MonitoredChannelService

logger = logging.getLogger(__name__)

# Service instances
admin_service = AdminService()
filter_service = FilterService()
selection_service = UserChannelSelectionService()
telegram_user_service = TelegramUserService()
monitored_channel_service = MonitoredChannelService()


@require_admin(AdminPermission.VIEW_STATS)
@log_admin_action("viewed_admin_panel", "admin_panel")
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main admin panel"""
    try:
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("📺 Управление каналами", callback_data="admin_channels")],
            [InlineKeyboardButton("👥 Управление пользователями", callback_data="admin_users")],
            [InlineKeyboardButton("📋 Логи системы", callback_data="admin_logs")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔧 <b>Панель администратора</b>\n\n"
            "Выберите раздел для управления:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error("Error in admin_panel: %s", e)
        await update.message.reply_text("❌ Ошибка при открытии панели администратора")


@require_admin(AdminPermission.VIEW_STATS)
@log_admin_action("viewed_statistics", "statistics")
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show system statistics"""
    try:
        stats = await admin_service.get_admin_stats()
        
        message = (
            "📊 <b>Статистика системы</b>\n\n"
            f"👥 <b>Пользователи:</b>\n"
            f"  • Всего: {stats.total_users}\n"
            f"  • Активных: {stats.active_users}\n\n"
            f"📺 <b>Каналы:</b>\n"
            f"  • Всего: {stats.total_channels}\n"
            f"  • Активных: {stats.active_channels}\n\n"
            f"🔍 <b>Фильтры:</b>\n"
            f"  • Всего: {stats.total_filters}\n\n"
            f"📨 <b>Сообщения:</b>\n"
            f"  • Обработано всего: {stats.total_messages_processed}\n"
            f"  • Сегодня: {stats.messages_today}\n\n"
            f"⏰ <b>Последняя активность:</b>\n"
            f"  • {stats.last_activity.strftime('%d.%m.%Y %H:%M') if stats.last_activity else 'Неизвестно'}"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error("Error in admin_stats: %s", e)
        await update.message.reply_text("❌ Ошибка при получении статистики")


@require_admin(AdminPermission.MANAGE_CHANNELS)
@log_admin_action("viewed_channels", "channels")
async def admin_channels(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage channels"""
    try:
        # Get all monitored channels
        subscriptions = await monitored_channel_service.get_all_channels()
        
        if not subscriptions:
            message = "📺 <b>Управление каналами</b>\n\n❌ Каналы не найдены"
        else:
            message = "📺 <b>Управление каналами</b>\n\n"
            for i, sub in enumerate(subscriptions[:10], 1):  # Show first 10
                status = "✅" if sub.is_active else "❌"
                topic_info = f" (топик {sub.topic_id})" if sub.topic_id else ""
                message += f"{i}. {status} {sub.channel_title}{topic_info}\n"
            
            if len(subscriptions) > 10:
                message += f"\n... и еще {len(subscriptions) - 10} каналов"
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить канал", callback_data="admin_add_channel")],
            [InlineKeyboardButton("📋 Список всех каналов", callback_data="admin_channels_list")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error("Error in admin_channels: %s", e)
        await update.message.reply_text("❌ Ошибка при получении списка каналов")


@require_admin(AdminPermission.MANAGE_USERS)
@log_admin_action("viewed_users", "users")
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage users"""
    try:
        # Get all admin users
        admin_users = await admin_service.get_all_admin_users()
        
        if not admin_users:
            message = "👥 <b>Управление пользователями</b>\n\n❌ Пользователи не найдены"
        else:
            message = "👥 <b>Управление пользователями</b>\n\n"
            for i, user in enumerate(admin_users[:10], 1):  # Show first 10
                status = "✅" if user.is_active else "❌"
                role_emoji = {
                    "user": "👤",
                    "moderator": "🛡️",
                    "admin": "👑",
                    "super_admin": "⭐"
                }.get(user.role.value, "❓")
                
                username = f"@{user.username}" if user.username else "Без username"
                message += f"{i}. {status} {role_emoji} {username} ({user.role.value})\n"
            
            if len(admin_users) > 10:
                message += f"\n... и еще {len(admin_users) - 10} пользователей"
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить админа", callback_data="admin_add_admin")],
            [InlineKeyboardButton("📋 Список всех пользователей", callback_data="admin_users_list")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error("Error in admin_users: %s", e)
        await update.message.reply_text("❌ Ошибка при получении списка пользователей")


@require_admin(AdminPermission.VIEW_LOGS)
@log_admin_action("viewed_logs", "logs")
async def admin_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show system logs"""
    try:
        # Get recent admin actions
        recent_actions = await admin_service.get_recent_admin_actions(limit=10)
        
        if not recent_actions:
            message = "📋 <b>Логи системы</b>\n\n❌ Логи не найдены"
        else:
            message = "📋 <b>Последние действия администраторов</b>\n\n"
            for action in recent_actions:
                timestamp = action.timestamp.strftime('%d.%m %H:%M')
                message += f"• {timestamp} - {action.action}\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin_logs")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error("Error in admin_logs: %s", e)
        await update.message.reply_text("❌ Ошибка при получении логов")


@require_super_admin
@log_admin_action("viewed_settings", "settings")
async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin settings (super admin only)"""
    try:
        message = (
            "⚙️ <b>Настройки системы</b>\n\n"
            "🔧 <b>Доступные настройки:</b>\n"
            "• Управление ролями пользователей\n"
            "• Настройки уведомлений\n"
            "• Конфигурация бота\n"
            "• Резервное копирование\n\n"
            "⚠️ <i>Эта функция в разработке</i>"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error("Error in admin_settings: %s", e)
        await update.message.reply_text("❌ Ошибка при открытии настроек")


@require_super_admin
@log_admin_action("promoted_user", "user")
async def promote_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Promote user to admin (super admin only)"""
    try:
        # Parse command arguments
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "❌ Использование: /promote <user_id_or_username> <role>\n"
                "Роли: user, moderator, admin, super_admin\n"
                "Примеры: /promote 123456789 admin\n"
                "         /promote @username moderator"
            )
            return
        
        try:
            user_identifier = context.args[0]
            role = UserRole(context.args[1])
        except (ValueError, KeyError):
            await update.message.reply_text(
                "❌ Неверный формат. Использование: /promote <user_id_or_username> <role>\n"
                "Роли: user, moderator, admin, super_admin"
            )
            return
        
        # Resolve user information
        user_info = await telegram_user_service.resolve_user_identifier(user_identifier)
        
        if not user_info:
            await update.message.reply_text(
                f"❌ Пользователь не найден: {user_identifier}\n"
                "Проверьте правильность ID или username"
            )
            return
        
        user_id = user_info["id"]
        username = user_info["username"]
        first_name = user_info["first_name"]
        last_name = user_info["last_name"]
        
        # Create or update admin user
        success = await admin_service.create_admin_user(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=role,
            created_by=update.effective_user.id
        )
        
        if success:
            display_name = f"{first_name} {last_name}".strip() or f"@{username}" or f"ID:{user_id}"
            await update.message.reply_text(
                f"✅ Пользователь {display_name} успешно назначен {role.value}"
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка при назначении роли пользователю {user_identifier}"
            )
        
    except Exception as e:
        logger.error("Error in promote_user: %s", e)
        await update.message.reply_text("❌ Ошибка при назначении роли пользователю")


@require_super_admin
@log_admin_action("created_super_admin", "user")
async def create_super_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create super admin user (super admin only)"""
    try:
        # Parse command arguments
        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "❌ Использование: /create_super_admin <user_id_or_username>\n"
                "Примеры: /create_super_admin 123456789\n"
                "         /create_super_admin @username"
            )
            return
        
        user_identifier = context.args[0]
        
        # Resolve user information
        user_info = await telegram_user_service.resolve_user_identifier(user_identifier)
        
        if not user_info:
            await update.message.reply_text(
                f"❌ Пользователь не найден: {user_identifier}\n"
                "Проверьте правильность ID или username"
            )
            return
        
        user_id = user_info["id"]
        username = user_info["username"]
        first_name = user_info["first_name"]
        last_name = user_info["last_name"]
        
        # Create super admin
        success = await admin_service.create_admin_user(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.SUPER_ADMIN,
            created_by=update.effective_user.id
        )
        
        if success:
            display_name = f"{first_name} {last_name}".strip() or f"@{username}" or f"ID:{user_id}"
            await update.message.reply_text(
                f"✅ Супер-администратор {display_name} успешно создан"
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка при создании супер-администратора {user_identifier}"
            )
        
    except Exception as e:
        logger.error("Error in create_super_admin: %s", e)
        await update.message.reply_text("❌ Ошибка при создании супер-администратора")


@require_super_admin
@log_admin_action("demoted_user", "user")
async def demote_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Demote user from admin (super admin only)"""
    try:
        # Parse command arguments
        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "❌ Использование: /demote <user_id_or_username>\n"
                "Примеры: /demote 123456789\n"
                "         /demote @username"
            )
            return
        
        user_identifier = context.args[0]
        
        # Resolve user information
        user_info = await telegram_user_service.resolve_user_identifier(user_identifier)
        
        if not user_info:
            await update.message.reply_text(
                f"❌ Пользователь не найден: {user_identifier}\n"
                "Проверьте правильность ID или username"
            )
            return
        
        user_id = user_info["id"]
        username = user_info["username"]
        first_name = user_info["first_name"]
        last_name = user_info["last_name"]
        
        # Demote user to regular user
        success = await admin_service.update_admin_user(
            user_id=user_id,
            role=UserRole.USER
        )
        
        if success:
            display_name = f"{first_name} {last_name}".strip() or f"@{username}" or f"ID:{user_id}"
            await update.message.reply_text(
                f"✅ Пользователь {display_name} понижен до обычного пользователя"
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка при понижении пользователя {user_identifier}"
            )
        
    except Exception as e:
        logger.error("Error in demote_user: %s", e)
        await update.message.reply_text("❌ Ошибка при понижении пользователя")
