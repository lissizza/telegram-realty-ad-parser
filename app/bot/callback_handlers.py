"""Callback query handlers: dispatcher + reprocess/refilter/channel callbacks"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.admin_callbacks import handle_admin_callback
from app.bot.command_handlers import start_command, stats_command, help_command
from app.bot.processing_handlers import reprocess_command, refilter_command
from app.services import get_telegram_service
from app.services.user_channel_selection_service import UserChannelSelectionService

logger = logging.getLogger(__name__)


def _build_channel_keyboard(channels: list) -> list:
    """Build InlineKeyboard rows from a list of available-channel dicts."""
    rows = []
    for ch in channels:
        channel_id = ch.get("channel_id", "")
        channel_title = ch.get("channel_title") or f"Канал {channel_id}"
        if len(channel_title) > 30:
            channel_title = channel_title[:27] + "..."

        topic_text = ""
        if ch.get("topic_id"):
            topic_title = ch.get("topic_title") or f"Топик {ch['topic_id']}"
            if len(topic_title) > 20:
                topic_title = topic_title[:17] + "..."
            topic_text = f" - {topic_title}"

        button_text = f"{channel_title}{topic_text}"
        topic_id_str = str(ch["topic_id"]) if ch.get("topic_id") else ""
        cb_data = f"reprocess_channel_{channel_id}_{topic_id_str}"
        rows.append([InlineKeyboardButton(button_text, callback_data=cb_data)])
    return rows


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries — main dispatcher"""
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

    if query.data.startswith("admin_"):
        await handle_admin_callback(update, context)
        return

    if query.data == "start":
        await start_command(update, context)
    elif query.data == "stats":
        await stats_command(update, context)
    elif query.data == "help":
        await help_command(update, context)
    elif query.data == "reprocess_menu":
        await reprocess_command(update, context)
    elif query.data == "refilter_menu":
        await refilter_command(update, context)
    elif query.data == "reprocess_channel_select":
        await _show_channel_selection(update, context)
    elif query.data == "reprocess_with_channels":
        await _show_reprocess_with_channels(update, context)
    elif query.data and query.data.startswith("reprocess_channel_"):
        await _handle_channel_reprocess_callback(update, context, query.data)
    elif query.data and query.data.startswith("reprocess_count_"):
        if query.data.count("_") == 2:  # reprocess_count_5
            await _handle_simple_reprocess_count_callback(update, context, query.data)
        else:  # reprocess_count_5_123456_789
            await _handle_reprocess_count_callback(update, context, query.data)
    elif query.data and query.data.startswith("reprocess_"):
        await _handle_reprocess_callback(update, context, query.data)
    elif query.data and query.data.startswith("refilter_"):
        await _handle_refilter_callback(update, context, query.data)
    elif query.data == "noop":
        pass


# ------------------------------------------------------------------
# Reprocess callbacks
# ------------------------------------------------------------------


async def _handle_reprocess_callback(update: Update, _: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle reprocess callback queries"""
    query = update.callback_query
    if not query:
        return

    try:
        if callback_data == "reprocess_5":
            num_messages, force = 5, False
        elif callback_data == "reprocess_10":
            num_messages, force = 10, False
        elif callback_data == "reprocess_20":
            num_messages, force = 20, False
        elif callback_data == "reprocess_50":
            num_messages, force = 50, False
        elif callback_data == "reprocess_force_10":
            num_messages, force = 10, True
        else:
            await query.edit_message_text("Неверная команда")
            return

        await query.edit_message_text(
            f"Обрабатываю {num_messages} последних сообщений{' (принудительно)' if force else ''}...\n\n"
            f"Пожалуйста, подождите..."
        )

        user_id = update.effective_user.id if update.effective_user else None

        telegram_service = get_telegram_service()
        if telegram_service:
            result = await telegram_service.reprocess_recent_messages(num_messages, force, user_id)
        else:
            await query.edit_message_text("Сервис обработки сообщений недоступен")
            return

        await query.edit_message_text(
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
        logger.error("Error in reprocess callback: %s", e)
        await query.edit_message_text(f"Произошла ошибка при обработке: {str(e)}")


# ------------------------------------------------------------------
# Refilter callbacks
# ------------------------------------------------------------------


async def _handle_refilter_callback(update: Update, _: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle refilter callback queries"""
    query = update.callback_query
    if not query:
        return

    try:
        if callback_data == "refilter_5":
            count = 5
        elif callback_data == "refilter_10":
            count = 10
        elif callback_data == "refilter_20":
            count = 20
        elif callback_data == "refilter_50":
            count = 50
        else:
            await query.answer("Неизвестная команда")
            return

        user_id = update.effective_user.id if update.effective_user else None
        if not user_id:
            await query.edit_message_text("Не удалось определить пользователя")
            return

        await query.edit_message_text(f"Фильтрую {count} объявлений...")

        try:
            telegram_service = get_telegram_service()
            if telegram_service is None:
                await query.edit_message_text("Сервис обработки сообщений недоступен")
                return

            result = await telegram_service.refilter_ads(count, user_id)

            result_text = "**Фильтрация завершена!**\n\n"
            result_text += "**Результаты:**\n"
            result_text += f"• Проверено объявлений: {result.get('total_checked', 0)}\n"
            result_text += f"• Соответствует фильтрам: {result.get('matched_filters', 0)}\n"
            result_text += f"• Переслано пользователю: {result.get('forwarded', 0)}\n"
            result_text += f"• Ошибок: {result.get('errors', 0)}"

            await query.edit_message_text(result_text, parse_mode="Markdown")

        except Exception as e:
            logger.error("Error calling refilter: %s", e)
            await query.edit_message_text(f"Ошибка при фильтрации: {str(e)}")

    except Exception as e:
        logger.error("Error in refilter callback: %s", e)
        await query.edit_message_text(f"Произошла ошибка при фильтрации: {str(e)}")


# ------------------------------------------------------------------
# Channel selection callbacks
# ------------------------------------------------------------------


async def _show_channel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show channel selection menu for reprocess"""
    query = update.callback_query
    if not query:
        return

    try:
        user_id = update.effective_user.id if update.effective_user else None
        if not user_id:
            await query.edit_message_text("Не удалось определить пользователя")
            return

        svc = UserChannelSelectionService()
        channels, _ = await svc.get_available_channels_for_user(user_id)
        selected = [ch for ch in channels if ch.get("is_selected")]
        if not selected:
            await query.edit_message_text("У вас нет подписок на каналы")
            return

        keyboard = _build_channel_keyboard(selected)
        keyboard.append([InlineKeyboardButton("Назад", callback_data="reprocess_menu")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "**Выберите канал для обработки**\n\n"
            "Выберите канал и топик для обработки сообщений:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error("Error in show_channel_selection: %s", e)
        await query.edit_message_text(f"Произошла ошибка: {str(e)}")


async def _show_reprocess_with_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show reprocess menu with channel selection and count input"""
    query = update.callback_query
    if not query:
        return

    try:
        user_id = update.effective_user.id if update.effective_user else None
        if not user_id:
            await query.edit_message_text("Не удалось определить пользователя")
            return

        svc = UserChannelSelectionService()
        channels, _ = await svc.get_available_channels_for_user(user_id)
        selected = [ch for ch in channels if ch.get("is_selected")]
        if not selected:
            await query.edit_message_text("У вас нет подписок на каналы")
            return

        keyboard = []

        keyboard.append([InlineKeyboardButton("5 сообщений", callback_data="reprocess_count_5")])
        keyboard.append([InlineKeyboardButton("10 сообщений", callback_data="reprocess_count_10")])
        keyboard.append([InlineKeyboardButton("20 сообщений", callback_data="reprocess_count_20")])
        keyboard.append([InlineKeyboardButton("50 сообщений", callback_data="reprocess_count_50")])
        keyboard.append([InlineKeyboardButton("100 сообщений", callback_data="reprocess_count_100")])

        keyboard.append([InlineKeyboardButton("─" * 20, callback_data="noop")])

        keyboard.extend(_build_channel_keyboard(selected))
        keyboard.append([InlineKeyboardButton("Назад", callback_data="reprocess_menu")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "**Обработка сообщений**\n\n"
            "**Выберите количество сообщений:**\n"
            "• 5, 10, 20, 50, 100 сообщений\n\n"
            "**Или выберите конкретный канал:**\n"
            "• Обработать все сообщения из выбранного канала\n\n"
            "**Команды:**\n"
            "• `/reprocess 10` - обработать 10 последних сообщений\n"
            "• `/reprocess 10 --force` - принудительно переобработать",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error("Error in show_reprocess_with_channels: %s", e)
        await query.edit_message_text(f"Произошла ошибка: {str(e)}")


async def _handle_simple_reprocess_count_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str
):
    """Handle simple reprocess count callback (reprocess_count_5)"""
    query = update.callback_query
    if not query:
        return

    try:
        parts = callback_data.split("_")
        if len(parts) != 3:
            await query.answer("Неверный формат данных")
            return

        count = int(parts[2])

        await query.edit_message_text(
            f"Обрабатываю {count} последних сообщений...\n" "Это может занять некоторое время."
        )

        telegram_service = get_telegram_service()
        if not telegram_service:
            await query.edit_message_text("Сервис недоступен")
            return

        user_id = update.effective_user.id if update.effective_user else None

        result = await telegram_service.reprocess_recent_messages(count, False, user_id)

        await query.edit_message_text(
            f"**Обработка завершена!**\n\n"
            f"**Результаты:**\n"
            f"• Обработано объявлений: {result['total_processed']}\n"
            f"• Пропущено (уже обработаны): {result['skipped']}\n"
            f"• Найдено объявлений о недвижимости: {result['real_estate_ads']}\n"
            f"• Отфильтровано спама: {result['spam_filtered']}\n"
            f"• Не недвижимость: {result['not_real_estate']}\n"
            f"• Соответствует фильтрам: {result['matched_filters']}\n"
            f"• Переслано пользователю: {result['forwarded']}\n"
            f"• Ошибок: {result['errors']}",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error("Error in handle_simple_reprocess_count_callback: %s", e)
        await query.edit_message_text(f"Произошла ошибка: {str(e)}")


async def _handle_channel_reprocess_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str
):
    """Handle channel-specific reprocess callback"""
    query = update.callback_query
    if not query:
        return

    try:
        parts = callback_data.split("_")
        if len(parts) < 3:
            await query.answer("Неверный формат данных")
            return

        channel_id = parts[2]
        topic_id = int(parts[3]) if parts[3] and parts[3].isdigit() else None

        keyboard = [
            [InlineKeyboardButton("5 сообщений", callback_data=f"reprocess_count_5_{channel_id}_{topic_id or ''}")],
            [InlineKeyboardButton("10 сообщений", callback_data=f"reprocess_count_10_{channel_id}_{topic_id or ''}")],
            [InlineKeyboardButton("20 сообщений", callback_data=f"reprocess_count_20_{channel_id}_{topic_id or ''}")],
            [InlineKeyboardButton("50 сообщений", callback_data=f"reprocess_count_50_{channel_id}_{topic_id or ''}")],
            [InlineKeyboardButton("Назад", callback_data="reprocess_channel_select")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        topic_text = f" (топик {topic_id})" if topic_id else ""
        await query.edit_message_text(
            f"**Обработка канала {channel_id}{topic_text}**\n\n"
            "Выберите количество сообщений для обработки:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error("Error in handle_channel_reprocess_callback: %s", e)
        await query.edit_message_text(f"Произошла ошибка: {str(e)}")


async def _handle_reprocess_count_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str
):
    """Handle reprocess count callback with channel"""
    query = update.callback_query
    if not query:
        return

    try:
        parts = callback_data.split("_")
        if len(parts) < 4:
            await query.answer("Неверный формат данных")
            return

        count = int(parts[2])
        channel_id = parts[3]
        topic_id = int(parts[4]) if parts[4] and parts[4].isdigit() else None

        topic_text = f" (топик {topic_id})" if topic_id else ""
        await query.edit_message_text(
            f"Обрабатываю {count} сообщений из канала {channel_id}{topic_text}...\n"
            "Это может занять некоторое время."
        )

        telegram_service = get_telegram_service()
        if not telegram_service:
            await query.edit_message_text("Сервис недоступен")
            return

        user_id = update.effective_user.id if update.effective_user else None

        result = await telegram_service.reprocess_recent_messages(count, False, user_id, channel_id)

        await query.edit_message_text(
            f"**Обработка завершена!**\n\n"
            f"**Результаты:**\n"
            f"• Обработано объявлений: {result['total_processed']}\n"
            f"• Пропущено (уже обработаны): {result['skipped']}\n"
            f"• Найдено объявлений о недвижимости: {result['real_estate_ads']}\n"
            f"• Отфильтровано спама: {result['spam_filtered']}\n"
            f"• Не недвижимость: {result['not_real_estate']}\n"
            f"• Соответствует фильтрам: {result['matched_filters']}\n"
            f"• Переслано пользователю: {result['forwarded']}\n"
            f"• Ошибок: {result['errors']}",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error("Error in handle_reprocess_count_callback: %s", e)
        await query.edit_message_text(f"Произошла ошибка: {str(e)}")
