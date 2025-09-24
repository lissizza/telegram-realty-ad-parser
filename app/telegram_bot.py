"""
Telegram bot with Web App integration for real estate search.

This module provides a Telegram bot that allows users to manage filters,
view statistics, and interact with the real estate search system through
a web application interface.
"""

import logging

import aiohttp
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.core.config import settings
from app.db.mongodb import mongodb
from app.services import get_telegram_service
from app.services.llm_service import LLMService
from app.services.user_service import user_service

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot with Web App integration"""

    def __init__(self):
        self.application = None
        self.bot_token = settings.TELEGRAM_BOT_TOKEN

    async def start_command(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if not update.message or not update.effective_user:
            return

        user = update.effective_user
        user_id = user.id
        username = user.username
        first_name = user.first_name

        # Auto-authorize the user (silently)
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
            [
                InlineKeyboardButton(
                    "⚙️ Настроить фильтры",
                    web_app=WebAppInfo(url=f"{settings.API_BASE_URL}/api/v1/static/simple-filters"),
                )
            ],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

    async def help_command(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
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
            "**3. Управляйте поиском**\n"
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

    async def settings_command(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command"""
        if not update.message:
            return

        keyboard = [
            [
                InlineKeyboardButton(
                    "⚙️ Настроить фильтры",
                    web_app=WebAppInfo(url=f"{settings.API_BASE_URL}/api/v1/static/simple-filters"),
                )
            ]
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

    async def stats_command(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        try:
            # Get statistics from API
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{settings.API_BASE_URL}/api/v1/statistics/") as response:
                    if response.status == 200:
                        stats_data = await response.json()

                        # Format statistics
                        stats_text = f"""📊 **Статистика поиска**

**Общая статистика:**
• 🔍 Всего обработано сообщений: {stats_data.get('total_posts', 0)}
• 🏠 Распарсено как недвижимость: {stats_data.get('parsed_ads', 0)}
• 🚫 Отфильтровано спама: {stats_data.get('spam_filtered', 0)}
• 📷 Только медиа (пропущено): {stats_data.get('media_only', 0)}
• ❌ Не недвижимость: {stats_data.get('non_real_estate', 0)}
• 🎯 Соответствует фильтрам: {stats_data.get('matched_filters', 0)}
• ✅ Переслано пользователю: {stats_data.get('forwarded_ads', 0)}
• 📡 Активных каналов: {stats_data.get('active_channels', 0)}
• ⚙️ Активных настроек: {stats_data.get('active_search_settings', 0)}

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

        # Handle both message and callback query
        if update.message:
            await update.message.reply_text(stats_text, parse_mode="Markdown")
        elif update.callback_query:
            await update.callback_query.edit_message_text(stats_text, parse_mode="Markdown")

    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /test command - test message processing"""
        if not update.message:
            return
        if not context.args:
            await update.message.reply_text(
                "Использование: /test <текст объявления>\n\n"
                "Пример: /test Сдаю 3-комнатную квартиру в центре Еревана, 250000 драм"
            )
            return

        test_text = " ".join(context.args)
        await update.message.reply_text(f"🧪 Тестирую обработку: {test_text}")

        # Process the test message
        await self.handle_message(update, context)

    async def myid_command(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        """Handle /myid command - get user ID and auto-authorize"""
        if not update.message or not update.effective_user:
            return

        user = update.effective_user
        user_id = user.id
        username = user.username
        first_name = user.first_name

        # Auto-authorize the user
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

    async def users_command(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        """Handle /users command - manage authorized users"""
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id

        # Check if user is authorized (simple check - first user or configured user)
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
            # Get all authorized users from database
            db = mongodb.get_database()
            users_collection = db.users
            users = await users_collection.find({"is_authorized": True}).to_list(length=None)

            if not users:
                await update.message.reply_text("📝 **Нет авторизованных пользователей**")
                return

            # Format users list
            users_text = "👥 **Авторизованные пользователи:**\n\n"
            for i, user in enumerate(users, 1):
                username = user.get("username", "Не указан")
                first_name = user.get("first_name", "Не указано")
                user_id = user["user_id"]

                users_text += f"{i}. **{first_name}**\n"
                users_text += f"   🆔 ID: `{user_id}`\n"
                users_text += f"   📝 @{username}\n\n"

            await update.message.reply_text(users_text, parse_mode="Markdown")

        except Exception as e:
            logger.error("Error in users command: %s", e)
            await update.message.reply_text(
                "❌ **Ошибка**\n\n" "Не удалось получить список пользователей.", parse_mode="Markdown"
            )

    async def reprocess_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reprocess command"""
        try:
            # Get message object (could be from callback or regular message)
            message = update.message or (update.callback_query.message if update.callback_query else None)
            if not message:
                logger.error("No message object available in update")
                return

            # Get number of messages to reprocess and force flag
            if not context.args or len(context.args) < 1 or len(context.args) > 2:
                # If no arguments provided, show interactive menu
                keyboard = [
                    [InlineKeyboardButton("🔄 5 групп", callback_data="reprocess_5")],
                    [InlineKeyboardButton("🔄 10 групп", callback_data="reprocess_10")],
                    [InlineKeyboardButton("🔄 20 групп", callback_data="reprocess_20")],
                    [InlineKeyboardButton("🔄 50 групп", callback_data="reprocess_50")],
                    [InlineKeyboardButton("🔄 Принудительно 10", callback_data="reprocess_force_10")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await message.reply_text(
                    "🔄 **Обработка сообщений**\n\nВыберите количество групп сообщений для обработки:",
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
                return

            try:
                num_messages = int(context.args[0])
                if num_messages <= 0 or num_messages > 100:
                    await message.reply_text("❌ Количество сообщений должно быть от 1 до 100")
                    return
            except ValueError:
                await message.reply_text("❌ Количество сообщений должно быть числом")
                return

            # Check for force flag
            force_reprocess = len(context.args) == 2 and context.args[1] == "--force"

            # Send processing started message
            mode_text = (
                "принудительно переобработать" if force_reprocess else "обработать (пропустить уже обработанные)"
            )
            processing_msg = await message.reply_text(
                f"🔄 Начинаю {mode_text} {num_messages} последних объявлений из канала...\n"
                "Это может занять некоторое время."
            )

            telegram_service = get_telegram_service()
            logger.info("telegram_service: %s", telegram_service)
            if telegram_service is None:
                logger.error("telegram_service is None!")
                if processing_msg and hasattr(processing_msg, "edit_text"):
                    await processing_msg.edit_text("❌ Сервис обработки сообщений недоступен")
                return

            # Reprocess messages
            result = await telegram_service.reprocess_recent_messages(num_messages, force_reprocess)

            # Update message with results
            if processing_msg and hasattr(processing_msg, "edit_text"):
                await processing_msg.edit_text(
                    f"✅ Обработка завершена!\n\n"
                    f"📊 Результаты:\n"
                    f"• 🔍 Обработано объявлений: {result['total_processed']}\n"
                    f"• ⏭️ Пропущено (уже обработаны): {result['skipped']}\n"
                    f"• 🏠 Найдено объявлений о недвижимости: {result['real_estate_ads']}\n"
                    f"• 🚫 Отфильтровано спама: {result['spam_filtered']}\n"
                    f"• ❌ Не недвижимость: {result['not_real_estate']}\n"
                    f"• 🎯 Соответствует фильтрам: {result['matched_filters']}\n"
                    f"• ✅ Переслано пользователю: {result['forwarded']}\n"
                    f"• ⚠️ Ошибок: {result['errors']}"
                )

        except Exception as e:
            logger.error("Error in reprocess command: %s", e)
            # Try to send error message to both message and callback_query
            if message:
                await message.reply_text(f"❌ Произошла ошибка при обработке: {str(e)}")
            elif update.callback_query:
                await update.callback_query.edit_message_text(f"❌ Произошла ошибка при обработке: {str(e)}")

    async def refilter_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /refilter command - filter existing ads without reprocessing"""
        try:
            # Get message object
            message = update.message or (update.callback_query.message if update.callback_query else None)
            if not message:
                logger.error("No message object available in update")
                return

            # Get number of ads to refilter
            if not context.args or len(context.args) < 1:
                # If no arguments provided, show interactive menu
                keyboard = [
                    [InlineKeyboardButton("🎯 5 объявлений", callback_data="refilter_5")],
                    [InlineKeyboardButton("🎯 10 объявлений", callback_data="refilter_10")],
                    [InlineKeyboardButton("🎯 20 объявлений", callback_data="refilter_20")],
                    [InlineKeyboardButton("🎯 50 объявлений", callback_data="refilter_50")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await message.reply_text(
                    "🎯 **Фильтрация объявлений**\n\n"
                    "Выберите количество объявлений для фильтрации:\n"
                    "*(Берет уже обработанные объявления из базы и проверяет их по текущим фильтрам)*",
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
                return

            # Parse arguments
            try:
                count = int(context.args[0])
                if count <= 0 or count > 100:
                    await message.reply_text("❌ Количество объявлений должно быть от 1 до 100")
                    return
            except ValueError:
                await message.reply_text("❌ Количество объявлений должно быть числом")
                return

            # No authorization check needed (same as other commands)

            # Show processing message
            processing_msg = await message.reply_text(f"🎯 Фильтрую {count} объявлений...")

            try:
                # Use telegram service
                telegram_service = get_telegram_service()

                if telegram_service is None:
                    if processing_msg and hasattr(processing_msg, "edit_text"):
                        await processing_msg.edit_text("❌ Сервис обработки сообщений недоступен")
                    return

                # Call refilter method directly
                result = await telegram_service.refilter_ads(count)

                # Format result message
                result_text = "✅ **Фильтрация завершена!**\n\n"
                result_text += "📊 **Результаты:**\n"
                result_text += f"• 🔍 Проверено объявлений: {result.get('total_checked', 0)}\n"
                result_text += f"• 🎯 Соответствует фильтрам: {result.get('matched_filters', 0)}\n"
                result_text += f"• ✅ Переслано пользователю: {result.get('forwarded', 0)}\n"
                result_text += f"• ⚠️ Ошибок: {result.get('errors', 0)}"

                if processing_msg and hasattr(processing_msg, "edit_text"):
                    await processing_msg.edit_text(result_text, parse_mode="Markdown")

            except Exception as e:
                logger.error("Error calling refilter: %s", e)
                if processing_msg and hasattr(processing_msg, "edit_text"):
                    await processing_msg.edit_text(f"❌ Ошибка при фильтрации: {str(e)}")

        except Exception as e:
            logger.error("Error in refilter_command: %s", e)
            if update.callback_query:
                await update.callback_query.edit_message_text(f"❌ Произошла ошибка при фильтрации: {str(e)}")
            else:
                if message:
                    await message.reply_text(f"❌ Произошла ошибка: {str(e)}")

    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analyze command"""
        if not update.message:
            return
        try:
            message = update.message

            # Get number of messages to analyze (default 50)
            limit = 50
            if context.args and len(context.args) >= 1:
                try:
                    limit = int(context.args[0])
                    if limit <= 0 or limit > 200:
                        await message.reply_text("❌ Количество сообщений должно быть от 1 до 200")
                        return
                except ValueError:
                    await message.reply_text("❌ Неверный формат. Используйте: /analyze [количество]")
                    return

            await message.reply_text(
                f"🔍 Анализирую структуру канала (последние {limit} сообщений)...\n"
                "Это может занять некоторое время..."
            )

            # Get monitored channels
            telegram_service = get_telegram_service()

            if telegram_service:
                channels = telegram_service._get_monitored_channels()  # pylint: disable=protected-access

                if not channels:
                    await message.reply_text("❌ Нет настроенных каналов для анализа")
                    return

                # Analyze first channel
                channel_id = int(channels[0])
                result = await telegram_service.analyze_channel_structure(channel_id, limit)
            else:
                await message.reply_text("❌ Сервис обработки сообщений недоступен")
                return

            if result:
                # Format results
                response = f"📊 **Анализ канала {channel_id}**\n\n"
                response += "📈 **Статистика:**\n"
                response += f"• Сообщений без топика (основной канал): {result['no_topic_count']}\n"
                response += f"• Всего топиков: {len(result['topic_stats'])}\n\n"

                if result["topic_stats"]:
                    response += "📋 **Топики:**\n"
                    for topic_id, count in result["topic_stats"].items():
                        response += f"• Топик {topic_id}: {count} сообщений\n"

                response += "\n🔍 **Примеры сообщений:**\n"
                for i, msg in enumerate(result["sample_messages"][:5], 1):
                    response += f"\n**{i}.** ID: {msg['id']}\n"
                    response += f"Текст: {msg['text']}...\n"
                    response += f"Reply to: {msg['reply_to']}\n"
                    response += f"Reply to top ID: {msg['reply_to_top_id']}\n"
                    response += f"Дата: {msg['date']}\n"
                    response += "─" * 30

                await message.reply_text(response)
            else:
                await message.reply_text("❌ Ошибка при анализе канала")

        except Exception as e:
            logger.error("Error in analyze command: %s", e)
            await message.reply_text(f"❌ Произошла ошибка: {str(e)}")

    async def handle_message(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages"""
        if not update.message or not update.message.text:
            return

        try:
            # Process message as real estate ad

            llm_service = LLMService()

            # Parse with LLM
            real_estate_ad = await llm_service.parse_with_llm(
                update.message.text, update.message.message_id, update.message.chat_id
            )

            if not real_estate_ad:
                await update.message.reply_text(
                    "❌ Не удалось распознать объявление о недвижимости. "
                    "Попробуйте отправить более подробное описание."
                )
                return

            # Save to database
            db = mongodb.get_database()
            ad_data = real_estate_ad.dict(exclude={"id"})
            result = await db.real_estate_ads.insert_one(ad_data)
            real_estate_ad.id = str(result.inserted_id)

            # Send response
            response = "🏠 **Объявление обработано!**\n\n"
            response += f"**Тип:** {real_estate_ad.property_type}\n"
            response += f"**Комнат:** {real_estate_ad.rooms_count}\n"
            response += f"**Площадь:** {real_estate_ad.area_sqm} кв.м\n"
            response += f"**Цена:** {real_estate_ad.price} {real_estate_ad.currency}\n"
            response += f"**Район:** {real_estate_ad.district}\n"
            response += f"**Уверенность:** {real_estate_ad.parsing_confidence:.2f}\n\n"
            response += f"**Текст:** {update.message.text[:200]}..."

            await update.message.reply_text(response, parse_mode="Markdown")

        except Exception as e:
            logger.error("Error processing message: %s", e)
            await update.message.reply_text("❌ Произошла ошибка при обработке сообщения. Попробуйте позже.")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        if not query:
            return
        await query.answer()

        logger.info(
            "DEBUG: Callback received: %s, update.message=%s, update.callback_query=%s",
            query.data,
            update.message,
            update.callback_query,
        )

        if query.data == "stats":
            await self.stats_command(update, context)
        elif query.data == "help":
            await self.help_command(update, context)
        elif query.data == "open_settings":
            # Open Web App directly
            keyboard = [
                [
                    InlineKeyboardButton(
                        "🏠 Управление фильтрами",
                        web_app=WebAppInfo(url=f"{settings.API_BASE_URL}/api/v1/static/simple-filters"),
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📡 Управление каналами",
                        web_app=WebAppInfo(url=f"{settings.API_BASE_URL}/api/v1/static/channel-management"),
                    )
                ],
                [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
                [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if query.message:
                await query.message.reply_text(
                    "🏠 **Управление недвижимостью**\n\nВыберите действие:",
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
        elif query.data and query.data.startswith("reprocess_"):
            await self.handle_reprocess_callback(update, context, query.data)
        elif query.data and query.data.startswith("refilter_"):
            await self.handle_refilter_callback(update, context, query.data)

    async def handle_reprocess_callback(self, update: Update, _: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Handle reprocess callback queries"""
        query = update.callback_query
        if not query:
            return

        try:
            # Parse callback data
            if callback_data == "reprocess_5":
                num_messages = 5
                force = False
            elif callback_data == "reprocess_10":
                num_messages = 10
                force = False
            elif callback_data == "reprocess_20":
                num_messages = 20
                force = False
            elif callback_data == "reprocess_50":
                num_messages = 50
                force = False
            elif callback_data == "reprocess_force_10":
                num_messages = 10
                force = True
            else:
                await query.edit_message_text("❌ Неверная команда")
                return

            # Show processing message
            await query.edit_message_text(
                f"🔄 Обрабатываю {num_messages} последних сообщений{' (принудительно)' if force else ''}...\n\n"
                f"⏳ Пожалуйста, подождите..."
            )

            # Use telegram service

            # Reprocess messages
            telegram_service = get_telegram_service()
            if telegram_service:
                result = await telegram_service.reprocess_recent_messages(num_messages, force)
            else:
                await query.edit_message_text("❌ Сервис обработки сообщений недоступен")
                return

            # Update message with results
            await query.edit_message_text(
                f"✅ Обработка завершена!\n\n"
                f"📊 Результаты:\n"
                f"• 🔍 Обработано объявлений: {result['total_processed']}\n"
                f"• ⏭️ Пропущено (уже обработаны): {result['skipped']}\n"
                f"• 🏠 Найдено объявлений о недвижимости: {result['real_estate_ads']}\n"
                f"• 🚫 Отфильтровано спама: {result['spam_filtered']}\n"
                f"• ❌ Не недвижимость: {result['not_real_estate']}\n"
                f"• 🎯 Соответствует фильтрам: {result['matched_filters']}\n"
                f"• ✅ Переслано пользователю: {result['forwarded']}\n"
                f"• ⚠️ Ошибок: {result['errors']}"
            )

        except Exception as e:
            logger.error("Error in reprocess callback: %s", e)
            await query.edit_message_text(f"❌ Произошла ошибка при обработке: {str(e)}")

    async def handle_refilter_callback(self, update: Update, _: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Handle refilter callback queries"""
        query = update.callback_query
        if not query:
            return

        try:
            # Parse callback data
            if callback_data == "refilter_5":
                count = 5
            elif callback_data == "refilter_10":
                count = 10
            elif callback_data == "refilter_20":
                count = 20
            elif callback_data == "refilter_50":
                count = 50
            else:
                await query.answer("❌ Неизвестная команда")
                return

            # No authorization check needed (same as other commands)

            # Show processing message
            await query.edit_message_text(f"🎯 Фильтрую {count} объявлений...")

            try:
                # Use telegram service

                telegram_service = get_telegram_service()
                if telegram_service is None:
                    await query.edit_message_text("❌ Сервис обработки сообщений недоступен")
                    return

                # Call refilter method directly
                result = await telegram_service.refilter_ads(count)

                # Format result message
                result_text = "✅ **Фильтрация завершена!**\n\n"
                result_text += "📊 **Результаты:**\n"
                result_text += f"• 🔍 Проверено объявлений: {result.get('total_checked', 0)}\n"
                result_text += f"• 🎯 Соответствует фильтрам: {result.get('matched_filters', 0)}\n"
                result_text += f"• ✅ Переслано пользователю: {result.get('forwarded', 0)}\n"
                result_text += f"• ⚠️ Ошибок: {result.get('errors', 0)}"

                await query.edit_message_text(result_text, parse_mode="Markdown")

            except Exception as e:
                logger.error("Error calling refilter: %s", e)
                await query.edit_message_text(f"❌ Ошибка при фильтрации: {str(e)}")

        except Exception as e:
            logger.error("Error in refilter callback: %s", e)
            await query.edit_message_text(f"❌ Произошла ошибка при фильтрации: {str(e)}")

    def setup_handlers(self):
        """Setup bot handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("settings", self.settings_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("test", self.test_command))
        self.application.add_handler(CommandHandler("reprocess", self.reprocess_command))
        self.application.add_handler(CommandHandler("refilter", self.refilter_command))
        self.application.add_handler(CommandHandler("analyze", self.analyze_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

    async def setup_commands_menu(self):
        """Setup bot commands menu"""
        commands = [
            BotCommand("start", "🏠 Главное меню"),
            BotCommand("help", "ℹ️ Справка"),
            BotCommand("settings", "⚙️ Настройки поиска"),
            BotCommand("stats", "📊 Статистика"),
        ]

        await self.application.bot.set_my_commands(commands)
        logger.info("Bot commands menu set up successfully")

    async def start_bot(self):
        """Start the bot"""
        try:
            if not self.bot_token:
                raise ValueError("Bot token is not configured")
            # Type assertion: we know bot_token is not None after the check above
            logger.info(
                "Initializing Telegram bot with token: %s...",
                self.bot_token[:10] if self.bot_token else "None",  # pylint: disable=unsubscriptable-object
            )  # type: ignore
            self.application = Application.builder().token(self.bot_token).build()
            self.setup_handlers()

            logger.info("Starting Telegram bot...")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()

            # Setup commands menu
            await self.setup_commands_menu()

            logger.info("Telegram bot started successfully")
        except Exception as e:
            logger.error("Failed to start Telegram bot: %s", e)
            logger.error(
                "Bot token: %s...",
                self.bot_token[:10] if self.bot_token else "None",  # pylint: disable=unsubscriptable-object
            )  # type: ignore
            raise

    async def stop_bot(self):
        """Stop the bot"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram bot stopped")


# Global bot instance
telegram_bot = TelegramBot()
