"""Command handlers: /start, /help, /settings, /stats, /myid, /users"""

import logging

import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

from app.core.config import settings
from app.db.mongodb import mongodb
from app.services.user_service import user_service
from app.bot.admin_decorators import is_admin

logger = logging.getLogger(__name__)
FILTERS_WEBAPP_VERSION = "20260213-1"


async def start_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    user_id = user.id
    username = user.username
    first_name = user.first_name

    await user_service.add_authorized_user(user_id, username, first_name)

    welcome_text = (
        f"🏠 **Привет, {first_name or 'друг'}!**\n\n"
        "Я помогу найти идеальную недвижимость для аренды без комиссий.\n\n"
        "**Что я умею:**\n"
        "• 🔍 Мониторить каналы с объявлениями\n"
        "• 🎯 Фильтровать по вашим критериям\n"
        "• 📱 Присылать только подходящие варианты\n\n"
        "**Давайте настроим поиск:**\n"
        "1. Нажмите 'Настроить фильтры' для выбора критериев\n"
        "2. Я начну искать подходящие объявления\n"
        "3. Буду присылать вам уведомления\n\n"
        "Готовы начать? 🚀"
    )

    keyboard = [
        [InlineKeyboardButton(
            "⚙️ Настроить фильтры",
            web_app=WebAppInfo(url=f"{settings.API_BASE_URL}/api/v1/static/simple-filters?v={FILTERS_WEBAPP_VERSION}"),
        )],
        [InlineKeyboardButton(
            "⚙️ Выбор каналов",
            web_app=WebAppInfo(url=f"{settings.API_BASE_URL}/api/v1/static/channel-selection"),
        )],
        [
            InlineKeyboardButton("🔄 Обработать сообщения", callback_data="reprocess_menu"),
            InlineKeyboardButton("🎯 Перефильтровать", callback_data="refilter_menu"),
        ],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")],
    ]

    if await is_admin(user_id):
        keyboard.append([InlineKeyboardButton("🔧 Админка", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    help_text = (
        "ℹ️ **Как пользоваться ботом**\n\n"
        "**1. Настройте фильтры**\n"
        "• Нажмите 'Настроить фильтры'\n"
        "• Выберите тип недвижимости, цену, район\n"
        "• Сохраните настройки\n\n"
        "**2. Получайте уведомления**\n"
        "• Я буду искать подходящие объявления\n"
        "• Присылать их вам в личные сообщения\n"
        "• Показывать только то, что подходит под ваши критерии\n\n"
        "**3. Сохраняйте заметки**\n"
        "• Пересылайте интересные объявления боту\n"
        "• Они сохранятся как заметки без парсинга\n"
        "• Используйте /test для парсинга с LLM (платно)\n\n"
        "**4. Управляйте поиском**\n"
        "• Изменяйте фильтры в любое время\n"
        "• Смотрите статистику поиска\n"
        "• Останавливайте/запускайте поиск\n\n"
        "**Поддерживаемые типы:**\n"
        "🏢 Квартиры • 🏡 Дома • 🚪 Комнаты • 🏨 Гостиничные номера\n\n"
        "**Районы Еревана:**\n"
        "Центр, Арабкир, Малатия, Аван, Нор-Норк и другие\n\n"
        "Готовы начать? Нажмите /start! 🚀"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def settings_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    keyboard = [
        [InlineKeyboardButton(
            "⚙️ Настроить фильтры",
            web_app=WebAppInfo(url=f"{settings.API_BASE_URL}/api/v1/static/simple-filters?v={FILTERS_WEBAPP_VERSION}"),
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "⚙️ **Настройка поиска**\n\n"
        "Здесь вы можете настроить критерии поиска:\n"
        "• Тип недвижимости\n"
        "• Ценовой диапазон\n"
        "• Район\n"
        "• Дополнительные параметры\n\n"
        "Нажмите кнопку ниже для настройки:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def stats_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{settings.API_BASE_URL}/api/v1/statistics/") as response:
                if response.status == 200:
                    stats_data = await response.json()
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
• 📅 Последнее обновление: {stats_data.get('last_updated', 'неизвестно')}

Используйте /settings для настройки поиска.
                    """
                else:
                    stats_text = "❌ Не удалось получить статистику. Попробуйте позже."
    except Exception as e:
        logger.error("Error getting statistics: %s", e)
        stats_text = "❌ Ошибка при получении статистики. Попробуйте позже."

    if update.message:
        await update.message.reply_text(stats_text, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(stats_text, parse_mode="Markdown")


async def myid_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    user_id = user.id
    username = user.username
    first_name = user.first_name

    success = await user_service.add_authorized_user(user_id, username, first_name)

    if success:
        await update.message.reply_text(
            f"✅ **Вы успешно авторизованы!**\n\n"
            f"🆔 **Ваш Telegram User ID:** `{user_id}`\n"
            f"👤 **Имя:** {first_name or 'Не указано'}\n"
            f"📝 **Username:** @{username or 'Не указан'}\n\n"
            f"Теперь вы будете получать уведомления о подходящих объявлениях!",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"❌ **Ошибка авторизации**\n\n"
            f"🆔 **Ваш Telegram User ID:** `{user_id}`\n\n"
            f"Попробуйте еще раз или обратитесь к администратору.",
            parse_mode="Markdown",
        )


async def users_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id

    authorized_users = await user_service.get_authorized_users()
    if not authorized_users or user_id not in authorized_users:
        await update.message.reply_text(
            "❌ **Доступ запрещен**\n\n"
            "Эта команда доступна только авторизованным пользователям.\n"
            "Используйте /myid для авторизации.",
            parse_mode="Markdown",
        )
        return

    try:
        db = mongodb.get_database()
        users_collection = db.users
        users = await users_collection.find({"is_authorized": True}).to_list(length=None)

        if not users:
            await update.message.reply_text("📝 **Нет авторизованных пользователей**")
            return

        users_text = "👥 **Авторизованные пользователи:**\n\n"
        for i, user in enumerate(users, 1):
            username = user.get("username", "Не указан")
            first_name = user.get("first_name", "Не указано")
            uid = user["user_id"]
            users_text += f"{i}. **{first_name}**\n"
            users_text += f"   🆔 ID: `{uid}`\n"
            users_text += f"   📝 @{username}\n\n"

        await update.message.reply_text(users_text, parse_mode="Markdown")

    except Exception as e:
        logger.error("Error in users command: %s", e)
        await update.message.reply_text(
            "❌ **Ошибка**\n\nНе удалось получить список пользователей.", parse_mode="Markdown"
        )
