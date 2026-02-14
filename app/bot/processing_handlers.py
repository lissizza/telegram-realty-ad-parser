"""Processing command handlers: /reprocess, /refilter"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.services import get_telegram_service

logger = logging.getLogger(__name__)


async def reprocess_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reprocess command with optional channel specification"""
    try:
        message = update.message or (update.callback_query.message if update.callback_query else None)
        if not message:
            logger.error("No message object available in update")
            return

        user_id = update.effective_user.id if update.effective_user else None

        if not context.args or len(context.args) < 1:
            keyboard = [
                [InlineKeyboardButton("5 сообщений", callback_data="reprocess_5")],
                [InlineKeyboardButton("10 сообщений", callback_data="reprocess_10")],
                [InlineKeyboardButton("20 сообщений", callback_data="reprocess_20")],
                [InlineKeyboardButton("50 сообщений", callback_data="reprocess_50")],
                [InlineKeyboardButton("Принудительно 10", callback_data="reprocess_force_10")],
                [InlineKeyboardButton("Выбрать канал", callback_data="reprocess_channel_select")],
                [InlineKeyboardButton("Каналы и количество", callback_data="reprocess_with_channels")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await message.reply_text(
                "**Обработка сообщений**\n\n"
                "Выберите количество сообщений для обработки или канал:\n\n"
                "**Доступные команды:**\n"
                "• `/reprocess 10` - обработать 10 последних сообщений\n"
                "• `/reprocess 10 --force` - принудительно переобработать\n"
                "• `/reprocess 10 --channel=1827102719` - обработать из конкретного канала",
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
            return

        try:
            num_messages = int(context.args[0])
            if num_messages <= 0 or num_messages > 100:
                await message.reply_text("Количество сообщений должно быть от 1 до 100")
                return
        except ValueError:
            await message.reply_text("Количество сообщений должно быть числом")
            return

        force_reprocess = False
        channel_id = None

        for arg in context.args[1:]:
            if arg == "--force":
                force_reprocess = True
            elif arg.startswith("--channel="):
                try:
                    channel_id = int(arg.split("=")[1])
                except (ValueError, IndexError):
                    await message.reply_text("Неверный формат channel_id. Используйте: --channel=1827102719")
                    return

        mode_text = (
            "принудительно переобработать" if force_reprocess else "обработать (пропустить уже обработанные)"
        )
        channel_text = f" из канала {channel_id}" if channel_id else ""

        processing_msg = await message.reply_text(
            f"Начинаю {mode_text} {num_messages} последних объявлений{channel_text}...\n"
            "Это может занять некоторое время."
        )

        telegram_service = get_telegram_service()
        logger.info("telegram_service: %s", telegram_service)
        if telegram_service is None:
            logger.error("telegram_service is None!")
            if processing_msg and hasattr(processing_msg, "edit_text"):
                await processing_msg.edit_text("Сервис обработки сообщений недоступен")
            return

        result = await telegram_service.reprocess_recent_messages(num_messages, force_reprocess, user_id, channel_id)

        if processing_msg and hasattr(processing_msg, "edit_text"):
            await processing_msg.edit_text(
                f"Обработка завершена!\n\n"
                f"Результаты:\n"
                f"• Обработано объявлений: {result['total_processed']}\n"
                f"• Пропущено (уже обработаны): {result['skipped']}\n"
                f"• Найдено объявлений о недвижимости: {result['real_estate_ads']}\n"
                f"• Отфильтровано спама: {result['spam_filtered']}\n"
                f"• Не недвижимость: {result['not_real_estate']}\n"
                f"• Соответствует фильтрам: {result['matched_filters']}\n"
                f"• Переслано пользователю: {result['forwarded']}\n"
                f"• Ошибок: {result['errors']}"
            )

    except Exception as e:
        logger.error("Error in reprocess command: %s", e)
        if message:
            await message.reply_text(f"Произошла ошибка при обработке: {str(e)}")
        elif update.callback_query:
            await update.callback_query.edit_message_text(f"Произошла ошибка при обработке: {str(e)}")


async def refilter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /refilter command - filter existing ads without reprocessing"""
    try:
        message = update.message or (update.callback_query.message if update.callback_query else None)
        if not message:
            logger.error("No message object available in update")
            return

        user_id = update.effective_user.id if update.effective_user else None

        if not context.args or len(context.args) < 1:
            keyboard = [
                [InlineKeyboardButton("5 объявлений", callback_data="refilter_5")],
                [InlineKeyboardButton("10 объявлений", callback_data="refilter_10")],
                [InlineKeyboardButton("20 объявлений", callback_data="refilter_20")],
                [InlineKeyboardButton("50 объявлений", callback_data="refilter_50")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await message.reply_text(
                "**Фильтрация объявлений**\n\n"
                "Выберите количество объявлений для фильтрации:\n"
                "*(Берет уже обработанные объявления из базы и проверяет их по текущим фильтрам)*",
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
            return

        try:
            count = int(context.args[0])
            if count <= 0 or count > 100:
                await message.reply_text("Количество объявлений должно быть от 1 до 100")
                return
        except ValueError:
            await message.reply_text("Количество объявлений должно быть числом")
            return

        processing_msg = await message.reply_text(f"Фильтрую {count} объявлений...")

        try:
            telegram_service = get_telegram_service()

            if telegram_service is None:
                if processing_msg and hasattr(processing_msg, "edit_text"):
                    await processing_msg.edit_text("Сервис обработки сообщений недоступен")
                return

            result = await telegram_service.refilter_ads(count, user_id)

            result_text = "**Фильтрация завершена!**\n\n"
            result_text += "**Результаты:**\n"
            result_text += f"• Проверено объявлений: {result.get('total_checked', 0)}\n"
            result_text += f"• Соответствует фильтрам: {result.get('matched_filters', 0)}\n"
            result_text += f"• Переслано пользователю: {result.get('forwarded', 0)}\n"
            result_text += f"• Ошибок: {result.get('errors', 0)}"

            if processing_msg and hasattr(processing_msg, "edit_text"):
                await processing_msg.edit_text(result_text, parse_mode="Markdown")

        except Exception as e:
            logger.error("Error calling refilter: %s", e)
            if processing_msg and hasattr(processing_msg, "edit_text"):
                await processing_msg.edit_text(f"Ошибка при фильтрации: {str(e)}")

    except Exception as e:
        logger.error("Error in refilter_command: %s", e)
        if update.callback_query:
            await update.callback_query.edit_message_text(f"Произошла ошибка при фильтрации: {str(e)}")
        elif message:
            await message.reply_text(f"Произошла ошибка: {str(e)}")
