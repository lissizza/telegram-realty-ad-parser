"""
Admin callback handlers for inline keyboards
"""

import logging

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

from app.core.config import settings
from app.services.admin_service import AdminService
from app.services.user_channel_selection_service import UserChannelSelectionService
from app.services.monitored_channel_service import MonitoredChannelService
from app.services.llm_quota_service import llm_quota_service
from app.bot.admin_decorators import is_super_admin
from app.services import get_telegram_service

logger = logging.getLogger(__name__)

# Service instances
admin_service = AdminService()
selection_service = UserChannelSelectionService()
monitored_channel_service = MonitoredChannelService()


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin callback queries"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    try:
        if data == "admin_panel":
            await admin_panel_callback(update, context)
        elif data == "admin_stats":
            await admin_stats_callback(update, context)
        elif data == "admin_users":
            await admin_users_callback(update, context)
        elif data == "admin_logs":
            await admin_logs_callback(update, context)
        elif data == "admin_settings":
            await admin_settings_callback(update, context)
        elif data == "admin_check_balance":
            await admin_check_balance_callback(update, context)
        elif data == "admin_channels":
            await admin_channels_callback(update, context)
        elif data == "admin_channels_list":
            await admin_channels_list_callback(update, context)
        elif data == "admin_add_channel":
            await admin_add_channel_callback(update, context)
        elif data == "admin_users_list":
            await admin_users_list_callback(update, context)
        elif data.startswith("admin_channel_"):
            await admin_channel_action_callback(update, context)
        elif data.startswith("admin_user_"):
            await admin_user_action_callback(update, context)
        else:
            await query.edit_message_text("❌ Неизвестная команда")
            
    except Exception as e:
        logger.error("Error handling admin callback %s: %s", data, e)
        await query.edit_message_text("❌ Произошла ошибка при обработке команды")


async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin panel callback"""
    user_id = update.effective_user.id
    web_app_url = f"{settings.API_BASE_URL}/api/v1/static/channel-selection?admin=true"
    stats_web_app_url = f"{settings.API_BASE_URL}/api/v1/static/admin-statistics?admin=true"
    llm_config_url = f"{settings.API_BASE_URL}/api/v1/static/llm-config-management?admin=true"
    
    # Check if user is super admin to show LLM quota button
    is_super = await is_super_admin(user_id)
    quota_status = llm_quota_service.get_status()
    quota_exceeded = quota_status.get("quota_exceeded", False)

    keyboard = [
        [InlineKeyboardButton("📊 Статистика", web_app=WebAppInfo(url=stats_web_app_url))],
        [InlineKeyboardButton("📺 Управление каналами", web_app=WebAppInfo(url=web_app_url))],
        [InlineKeyboardButton("👥 Управление пользователями", callback_data="admin_users")],
        [InlineKeyboardButton("📋 Логи системы", callback_data="admin_logs")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
    ]
    
    # Add LLM management buttons for super admins
    if is_super:
        keyboard.append([InlineKeyboardButton("🤖 Управление LLM движками", web_app=WebAppInfo(url=llm_config_url))])
        quota_emoji = "❌" if quota_exceeded else "✅"
        quota_text = f"{quota_emoji} Проверить баланс LLM"
        keyboard.append([InlineKeyboardButton(quota_text, callback_data="admin_check_balance")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="start")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "🔧 <b>Панель администратора</b>\n\n"
        "Выберите раздел для управления:",
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin stats callback - show search statistics"""
    try:
        # Get statistics from API (same as user stats command)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{settings.API_BASE_URL}/api/v1/statistics/") as response:
                if response.status == 200:
                    stats_data = await response.json()

                    # Format statistics
                    stats_text = f"""📊 **Статистика поиска**

**Общая статистика:**
• 🔍 Всего обработано сообщений: {stats_data.get('total_posts', 0)}
• 🏠 Распарсено как недвижимость: {stats_data.get('parsed_ads', 0)}
• ❌ Не недвижимость: {stats_data.get('non_real_estate', 0)}
• 🔄 Дубликаты: {stats_data.get('duplicates', 0)}
• 👥 Зарегистрированных пользователей: {stats_data.get('registered_users', 0)}
• 🎯 Соответствует фильтрам (всего): {stats_data.get('matched_filters', 0)}
• ✅ Переслано всем пользователям: {stats_data.get('forwarded_ads', 0)}
• 📡 Активных каналов: {stats_data.get('active_channels', 0)}

**Статус системы:**
• 🔄 Парсинг: {stats_data.get('parsing_status', 'неизвестно')}
• 🤖 Бот: {'активен' if stats_data.get('bot_status') == 'active' else 'неактивен'}

**Расходы на LLM:**
• 💰 Общая стоимость: ${stats_data.get('total_llm_cost', 0):.4f}
• 📊 Средняя стоимость за объявление: ${stats_data.get('avg_cost_per_ad', 0):.4f}

**Последняя активность:**
• 📅 Последнее обновление: {stats_data.get('last_updated', 'неизвестно')}"""
                else:
                    stats_text = "❌ Не удалось получить статистику. Попробуйте позже."

    except Exception as e:
        logger.error("Error getting statistics: %s", e)
        stats_text = "❌ Ошибка при получении статистики. Попробуйте позже."

    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        stats_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )



async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin users callback"""
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
            
            # Create display name
            display_name = ""
            if user.first_name or user.last_name:
                display_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            elif user.username:
                display_name = f"@{user.username}"
            else:
                display_name = f"ID:{user.user_id}"
            
            message += f"{i}. {status} {role_emoji} {display_name} ({user.role.value})\n"
        
        if len(admin_users) > 10:
            message += f"\n... и еще {len(admin_users) - 10} пользователей"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить админа", callback_data="admin_add_admin")],
        [InlineKeyboardButton("📋 Список всех пользователей", callback_data="admin_users_list")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def admin_logs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin logs callback"""
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
    
    await update.callback_query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def admin_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin settings callback"""
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
    
    await update.callback_query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def admin_check_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin check LLM balance callback"""
    user_id = update.effective_user.id
    
    # Check if user is super admin
    if not await is_super_admin(user_id):
        await update.callback_query.edit_message_text(
            "❌ Эта функция доступна только супер-администраторам",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")
            ]])
        )
        return
    
    # Show checking message
    await update.callback_query.edit_message_text(
        "🔍 <b>Проверка баланса LLM</b>\n\n"
        "⏳ Выполняется проверка баланса...",
        parse_mode='HTML'
    )
    
    try:
        # Perform balance check
        balance_available = await llm_quota_service.check_balance()
        quota_status = llm_quota_service.get_status()
        quota_exceeded = quota_status.get("quota_exceeded", False)
        
        if balance_available:
            message = (
                "✅ <b>Баланс LLM восстановлен!</b>\n\n"
                "Обработка сообщений возобновлена автоматически.\n\n"
            )
            
            # Automatically trigger reprocessing of stuck messages
            try:
                telegram_service = get_telegram_service()
                await telegram_service._reprocess_stuck_messages()
                message += "🔄 Запущена обработка застрявших сообщений."
            except Exception as e:
                logger.error("Error reprocessing stuck messages after balance restore: %s", e)
                message += "⚠️ Ошибка при запуске обработки застрявших сообщений."
        else:
            message = (
                "❌ <b>Баланс LLM все еще исчерпан</b>\n\n"
                "Проверьте баланс и пополните счет.\n\n"
                "Следующая автоматическая проверка через 15 минут."
            )
        
        # Add status info
        last_check = quota_status.get("last_balance_check_time")
        if last_check:
            message += f"\n\n⏰ Последняя проверка: {last_check}"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Проверить снова", callback_data="admin_check_balance")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error("Error checking LLM balance: %s", e)
        await update.callback_query.edit_message_text(
            f"❌ <b>Ошибка при проверке баланса</b>\n\n"
            f"Ошибка: {str(e)}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")
            ]])
        )


async def admin_channels_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin channels callback - open web interface directly"""
    user_id = update.effective_user.id
    web_app_url = f"{settings.API_BASE_URL}/api/v1/static/channel-selection"
    
    await update.callback_query.edit_message_text(
        "📺 <b>Управление каналами</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Открыть веб-интерфейс", web_app=WebAppInfo(url=web_app_url))
        ]])
    )


async def admin_channels_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin channels list callback"""
    channels = await monitored_channel_service.get_all_channels()
    
    if not channels:
        message = "📋 <b>Список всех каналов</b>\n\n❌ Каналы не найдены"
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
    else:
        message = "📋 <b>Список всех каналов</b>\n\n"
        keyboard = []

        for i, channel in enumerate(channels, 1):
            status = "✅" if channel.is_active else "❌"
            topic_info = f" (топик {channel.topic_title or channel.topic_id})" if channel.topic_id else ""

            # Format channel name
            channel_name = channel.channel_title or channel.channel_username or f"ID:{channel.channel_id}"

            # Format short name for button
            if channel.channel_username:
                short_name = f"@{channel.channel_username.lstrip('@')}"
            else:
                short_name = f"ID:{channel.channel_id}"

            channel_text = f"{i}. {status} {short_name}{topic_info}"

            # Truncate long text
            if len(channel_text) > 50:
                channel_text = channel_text[:47] + "..."

            keyboard.append([
                InlineKeyboardButton(
                    channel_text,
                    callback_data=f"admin_channel_{channel.id}"
                )
            ])

        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def admin_add_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin add channel callback - show web interface link"""
    user_id = update.effective_user.id
    web_app_url = f"{settings.API_BASE_URL}/api/v1/static/channel-selection"
    
    message = (
        "➕ <b>Добавить новый канал</b>\n\n"
        "Для добавления канала используйте веб-интерфейс.\n"
        "Нажмите кнопку ниже для перехода:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🌐 Открыть веб-интерфейс", web_app=WebAppInfo(url=web_app_url))],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def admin_users_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin users list callback"""
    admin_users = await admin_service.get_all_admin_users()
    
    if not admin_users:
        message = "📋 <b>Список всех пользователей</b>\n\n❌ Пользователи не найдены"
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_users")]]
    else:
        message = "📋 <b>Список всех пользователей</b>\n\n"
        keyboard = []
        
        for i, user in enumerate(admin_users, 1):
            status = "✅" if user.is_active else "❌"
            role_emoji = {
                "user": "👤",
                "moderator": "🛡️",
                "admin": "👑",
                "super_admin": "⭐"
            }.get(user.role.value, "❓")
            
            username = f"@{user.username}" if user.username else "Без username"
            user_text = f"{i}. {status} {role_emoji} {username} ({user.role.value})"
            
            # Truncate long text
            if len(user_text) > 50:
                user_text = user_text[:47] + "..."
            
            keyboard.append([
                InlineKeyboardButton(
                    user_text,
                    callback_data=f"admin_user_{user.user_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_users")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def admin_channel_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin channel action callback"""
    # Parse channel ID from callback data
    channel_id = update.callback_query.data.replace("admin_channel_", "")
    
    # Get channel
    channel = await monitored_channel_service.get_channel(channel_id)
    
    if not channel:
        await update.callback_query.edit_message_text("❌ Канал не найден")
        return
    
    message = (
        f"📺 <b>Информация о канале</b>\n\n"
        f"<b>Название:</b> {channel.channel_title}\n"
        f"<b>ID канала:</b> {channel.channel_id}\n"
        f"<b>Username:</b> @{channel.channel_username}\n"
        f"<b>Топик:</b> {channel.topic_id or 'Не указан'}\n"
        f"<b>Статус:</b> {'Активен' if channel.is_active else 'Неактивен'}\n"
        f"<b>Создан:</b> {channel.created_at.strftime('%d.%m.%Y %H:%M')}"
    )
    
    keyboard = [
        [
            InlineKeyboardButton(
                "❌ Деактивировать" if channel.is_active else "✅ Активировать",
                callback_data=f"admin_toggle_channel_{channel.id}"
            )
        ],
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"admin_delete_channel_{channel.id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_channels_list")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def admin_user_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin user action callback"""
    # Parse user ID from callback data
    user_id = int(update.callback_query.data.replace("admin_user_", ""))
    
    # Get admin user
    admin_user = await admin_service.get_admin_user(user_id)
    
    if not admin_user:
        await update.callback_query.edit_message_text("❌ Пользователь не найден")
        return
    
    message = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"<b>ID:</b> {admin_user.user_id}\n"
        f"<b>Username:</b> @{admin_user.username or 'Не указан'}\n"
        f"<b>Имя:</b> {admin_user.first_name or 'Не указано'}\n"
        f"<b>Фамилия:</b> {admin_user.last_name or 'Не указано'}\n"
        f"<b>Роль:</b> {admin_user.role.value}\n"
        f"<b>Статус:</b> {'Активен' if admin_user.is_active else 'Неактивен'}\n"
        f"<b>Создан:</b> {admin_user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"<b>Последняя активность:</b> {admin_user.last_activity.strftime('%d.%m.%Y %H:%M') if admin_user.last_activity else 'Неизвестно'}"
    )
    
    keyboard = [
        [
            InlineKeyboardButton(
                "❌ Деактивировать" if admin_user.is_active else "✅ Активировать",
                callback_data=f"admin_toggle_user_{admin_user.user_id}"
            )
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_users_list")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
