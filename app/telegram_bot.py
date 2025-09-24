import logging
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from app.core.config import settings

logger = logging.getLogger(__name__)

class TelegramBot:
    """Telegram bot with Web App integration"""
    
    def __init__(self):
        self.application = None
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        keyboard = [
            [InlineKeyboardButton("🏠 Управление фильтрами", web_app={"url": f"{settings.API_BASE_URL}/api/v1/static/simple-filters"})],
            [InlineKeyboardButton("📡 Управление каналами", web_app={"url": f"{settings.API_BASE_URL}/api/v1/static/channel-management"})],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🏠 Добро пожаловать в бот поиска недвижимости!\n\n"
            "Я помогу вам найти подходящие объявления о сдаче недвижимости в Ереване.\n\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🏠 **Бот поиска недвижимости**

**Основные функции:**
• 🔍 Автоматический поиск объявлений
• ⚙️ Настройка критериев поиска
• 📊 Статистика найденных объявлений
• 🔔 Уведомления о новых предложениях

**Команды:**
/start - Главное меню
/help - Эта справка
/settings - Настройки поиска
/stats - Статистика
/reprocess N [--force] - Обработать N последних сообщений из канала
/analyze [N] - Анализ структуры канала (по умолчанию 50 сообщений)

**Как использовать:**
1. Нажмите "Настройки поиска"
2. Выберите режим поиска:
   - 📋 Структурированный (по параметрам)
   - 💬 Произвольный запрос
3. Настройте критерии
4. Сохраните настройку
5. Бот будет автоматически искать подходящие объявления

**Поддерживаемые типы недвижимости:**
• 🏢 Квартиры
• 🏡 Дома
• 🚪 Комнаты
• 🏨 Гостиничные номера

**Районы Еревана:**
• Центр, Кентрон
• Арабкир, Малатия
• Аван, Нор-Норк
• И другие

По всем вопросам обращайтесь к администратору.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command"""
        keyboard = [
            [InlineKeyboardButton("🏠 Открыть управление фильтрами", web_app={"url": f"{settings.API_BASE_URL}/api/v1/static/simple-filters"})]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🏠 **Управление фильтрами**\n\n"
            "Нажмите кнопку ниже, чтобы открыть интерфейс управления фильтрами:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            logger.error(f"Error getting statistics: {e}")
            stats_text = "❌ Ошибка при получении статистики. Попробуйте позже."
        
        # Handle both message and callback query
        if update.message:
            await update.message.reply_text(stats_text, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.edit_message_text(stats_text, parse_mode='Markdown')
    
    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /test command - test message processing"""
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
    
    async def myid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /myid command - get user ID"""
        user_id = update.effective_user.id
        await update.message.reply_text(
            f"🆔 **Ваш Telegram User ID:** `{user_id}`\n\n"
            f"Добавьте эту строку в ваш .env файл:\n"
            f"`TELEGRAM_USER_ID={user_id}`",
            parse_mode='Markdown'
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
                    [InlineKeyboardButton("🔄 Принудительно 10", callback_data="reprocess_force_10")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await message.reply_text(
                    "🔄 **Обработка сообщений**\n\n"
                    "Выберите количество групп сообщений для обработки:",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                return
            
            try:
                num_messages = int(context.args[0])
                if num_messages <= 0 or num_messages > 100:
                    await message.reply_text(
                        "❌ Количество сообщений должно быть от 1 до 100"
                    )
                    return
            except ValueError:
                await message.reply_text(
                    "❌ Количество сообщений должно быть числом"
                )
                return
            
            # Check for force flag
            force_reprocess = len(context.args) == 2 and context.args[1] == "--force"
            
            # Send processing started message
            mode_text = "принудительно переобработать" if force_reprocess else "обработать (пропустить уже обработанные)"
            processing_msg = await message.reply_text(
                f"🔄 Начинаю {mode_text} {num_messages} последних объявлений из канала...\n"
                "Это может занять некоторое время."
            )
            
            # Import telegram service
            from app.main import telegram_service
            logger.info(f"telegram_service: {telegram_service}")
            if telegram_service is None:
                logger.error("telegram_service is None!")
                await processing_msg.edit_text("❌ Сервис обработки сообщений недоступен")
                return
            
            # Reprocess messages
            result = await telegram_service.reprocess_recent_messages(num_messages, force_reprocess)
            
            # Update message with results
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
            logger.error(f"Error in reprocess command: {e}")
            # Try to send error message to both message and callback_query
            if message:
                await message.reply_text(
                    f"❌ Произошла ошибка при обработке: {str(e)}"
                )
            elif update.callback_query:
                await update.callback_query.edit_message_text(
                    f"❌ Произошла ошибка при обработке: {str(e)}"
                )
    
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
                    [InlineKeyboardButton("🎯 50 объявлений", callback_data="refilter_50")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await message.reply_text(
                    "🎯 **Фильтрация объявлений**\n\n"
                    "Выберите количество объявлений для фильтрации:\n"
                    "*(Берет уже обработанные объявления из базы и проверяет их по текущим фильтрам)*",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
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
                # Import telegram service
                from app.main import telegram_service
                if telegram_service is None:
                    await processing_msg.edit_text("❌ Сервис обработки сообщений недоступен")
                    return
                
                # Call refilter method directly
                result = await telegram_service.refilter_ads(count)
                
                # Format result message
                result_text = f"✅ **Фильтрация завершена!**\n\n"
                result_text += f"📊 **Результаты:**\n"
                result_text += f"• 🔍 Проверено объявлений: {result.get('total_checked', 0)}\n"
                result_text += f"• 🎯 Соответствует фильтрам: {result.get('matched_filters', 0)}\n"
                result_text += f"• ✅ Переслано пользователю: {result.get('forwarded', 0)}\n"
                result_text += f"• ⚠️ Ошибок: {result.get('errors', 0)}"
                
                await processing_msg.edit_text(result_text, parse_mode='Markdown')
                            
            except Exception as e:
                logger.error(f"Error calling refilter: {e}")
                await processing_msg.edit_text(f"❌ Ошибка при фильтрации: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in refilter_command: {e}")
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    f"❌ Произошла ошибка при фильтрации: {str(e)}"
                )
            else:
                await message.reply_text(f"❌ Произошла ошибка: {str(e)}")
    
    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analyze command"""
        try:
            message = update.message
            if not message:
                logger.error("No message object available in update")
                return
            
            # Get number of messages to analyze (default 50)
            limit = 50
            if context.args and len(context.args) >= 1:
                try:
                    limit = int(context.args[0])
                    if limit <= 0 or limit > 200:
                        await message.reply_text(
                            "❌ Количество сообщений должно быть от 1 до 200"
                        )
                        return
                except ValueError:
                    await message.reply_text(
                        "❌ Неверный формат. Используйте: /analyze [количество]"
                    )
                    return
            
            await message.reply_text(
                f"🔍 Анализирую структуру канала (последние {limit} сообщений)...\n"
                "Это может занять некоторое время..."
            )
            
            # Get monitored channels
            from app.main import telegram_service
            channels = telegram_service._get_monitored_channels()
            
            if not channels:
                await message.reply_text("❌ Нет настроенных каналов для анализа")
                return
            
            # Analyze first channel
            channel_id = int(channels[0])
            result = await telegram_service.analyze_channel_structure(channel_id, limit)
            
            if result:
                # Format results
                response = f"📊 **Анализ канала {channel_id}**\n\n"
                response += f"📈 **Статистика:**\n"
                response += f"• Сообщений без топика (основной канал): {result['no_topic_count']}\n"
                response += f"• Всего топиков: {len(result['topic_stats'])}\n\n"
                
                if result['topic_stats']:
                    response += f"📋 **Топики:**\n"
                    for topic_id, count in result['topic_stats'].items():
                        response += f"• Топик {topic_id}: {count} сообщений\n"
                
                response += f"\n🔍 **Примеры сообщений:**\n"
                for i, msg in enumerate(result['sample_messages'][:5], 1):
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
            logger.error(f"Error in analyze command: {e}")
            await message.reply_text(f"❌ Произошла ошибка: {str(e)}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages"""
        if update.message and update.message.text:
            try:
                # Process message as real estate ad
                from app.services.llm_service import LLMService
                from app.services.parser_service import ParserService
                from app.db.mongodb import mongodb
                
                llm_service = LLMService()
                parser_service = ParserService()
                
                # Try LLM parsing first
                real_estate_ad = await llm_service.parse_with_llm(
                    update.message.text, 
                    update.message.message_id, 
                    update.message.chat_id
                )
                
                # Fallback to regex parsing
                if not real_estate_ad:
                    real_estate_ad = await parser_service.parse_real_estate_ad(
                        update.message.text,
                        update.message.message_id,
                        update.message.chat_id
                    )
                
                if real_estate_ad:
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
                    response += f"**Цена:** {real_estate_ad.price_amd} драм\n"
                    response += f"**Район:** {real_estate_ad.district}\n"
                    response += f"**Уверенность:** {real_estate_ad.parsing_confidence:.2f}\n\n"
                    response += f"**Текст:** {update.message.text[:200]}..."
                    
                    await update.message.reply_text(response, parse_mode='Markdown')
                else:
                    await update.message.reply_text(
                        "❌ Не удалось распознать объявление о недвижимости. "
                        "Попробуйте отправить более подробное описание."
                    )
                    
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await update.message.reply_text(
                    "❌ Произошла ошибка при обработке сообщения. Попробуйте позже."
                )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        
        logger.info(f"DEBUG: Callback received: {query.data}, update.message={update.message}, update.callback_query={update.callback_query}")
        
        if query.data == "stats":
            await self.stats_command(update, context)
        elif query.data == "help":
            await self.help_command(update, context)
        elif query.data == "open_settings":
            # Open Web App directly
            keyboard = [
                [InlineKeyboardButton("🏠 Управление фильтрами", web_app={"url": f"{settings.API_BASE_URL}/api/v1/static/simple-filters"})],
                [InlineKeyboardButton("📡 Управление каналами", web_app={"url": f"{settings.API_BASE_URL}/api/v1/static/channel-management"})],
                [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
                [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.reply_text(
                "🏠 **Управление недвижимостью**\n\n"
                "Выберите действие:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        elif query.data.startswith("reprocess_"):
            await self.handle_reprocess_callback(update, context, query.data)
        elif query.data.startswith("refilter_"):
            await self.handle_refilter_callback(update, context, query.data)
    
    async def handle_reprocess_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Handle reprocess callback queries"""
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
                await update.callback_query.edit_message_text("❌ Неверная команда")
                return
            
            # Show processing message
            processing_msg = await update.callback_query.edit_message_text(
                f"🔄 Обрабатываю {num_messages} последних сообщений{' (принудительно)' if force else ''}...\n\n"
                f"⏳ Пожалуйста, подождите..."
            )
            
            # Import telegram service
            from app.main import telegram_service
            
            # Reprocess messages
            result = await telegram_service.reprocess_recent_messages(num_messages, force)
            
            # Update message with results
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
            logger.error(f"Error in reprocess callback: {e}")
            await update.callback_query.edit_message_text(
                f"❌ Произошла ошибка при обработке: {str(e)}"
            )
    
    async def handle_refilter_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Handle refilter callback queries"""
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
                await update.callback_query.answer("❌ Неизвестная команда")
                return
            
            # No authorization check needed (same as other commands)
            
            # Show processing message
            await update.callback_query.edit_message_text(f"🎯 Фильтрую {count} объявлений...")
            
            try:
                # Import telegram service
                from app.main import telegram_service
                if telegram_service is None:
                    await update.callback_query.edit_message_text("❌ Сервис обработки сообщений недоступен")
                    return
                
                # Call refilter method directly
                result = await telegram_service.refilter_ads(count)
                
                # Format result message
                result_text = f"✅ **Фильтрация завершена!**\n\n"
                result_text += f"📊 **Результаты:**\n"
                result_text += f"• 🔍 Проверено объявлений: {result.get('total_checked', 0)}\n"
                result_text += f"• 🎯 Соответствует фильтрам: {result.get('matched_filters', 0)}\n"
                result_text += f"• ✅ Переслано пользователю: {result.get('forwarded', 0)}\n"
                result_text += f"• ⚠️ Ошибок: {result.get('errors', 0)}"
                
                await update.callback_query.edit_message_text(result_text, parse_mode='Markdown')
                            
            except Exception as e:
                logger.error(f"Error calling refilter: {e}")
                await update.callback_query.edit_message_text(f"❌ Ошибка при фильтрации: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in refilter callback: {e}")
            await update.callback_query.edit_message_text(
                f"❌ Произошла ошибка при фильтрации: {str(e)}"
            )
    
    def setup_handlers(self):
        """Setup bot handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("settings", self.settings_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("test", self.test_command))
        self.application.add_handler(CommandHandler("myid", self.myid_command))
        self.application.add_handler(CommandHandler("reprocess", self.reprocess_command))
        self.application.add_handler(CommandHandler("refilter", self.refilter_command))
        self.application.add_handler(CommandHandler("analyze", self.analyze_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
    
    async def setup_commands_menu(self):
        """Setup bot commands menu"""
        from telegram import BotCommand
        
        commands = [
            BotCommand("start", "🏠 Главное меню"),
            BotCommand("help", "ℹ️ Справка"),
            BotCommand("settings", "⚙️ Настройки поиска"),
            BotCommand("stats", "📊 Статистика"),
            BotCommand("reprocess", "🔄 Обработать сообщения"),
            BotCommand("refilter", "🎯 Фильтровать объявления"),
            BotCommand("analyze", "🔍 Анализ канала"),
            BotCommand("myid", "🆔 Мой ID"),
        ]
        
        await self.application.bot.set_my_commands(commands)
        logger.info("Bot commands menu set up successfully")
    
    async def start_bot(self):
        """Start the bot"""
        try:
            logger.info(f"Initializing Telegram bot with token: {self.bot_token[:10]}...")
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
            logger.error(f"Failed to start Telegram bot: {e}")
            logger.error(f"Bot token: {self.bot_token[:10]}...")
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
