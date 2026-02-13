"""Message handlers for non-command messages (notes)"""

import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from app.db.mongodb import mongodb

logger = logging.getLogger(__name__)


async def handle_message(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages - save as notes without LLM parsing"""
    if not update.message or not update.message.text:
        return

    try:
        is_forwarded = update.message.forward_from is not None or update.message.forward_from_chat is not None

        db = mongodb.get_database()

        note_data = {
            "user_id": update.effective_user.id,
            "message_id": update.message.message_id,
            "chat_id": update.message.chat_id,
            "text": update.message.text,
            "is_forwarded": is_forwarded,
            "forward_from": str(update.message.forward_from.id) if update.message.forward_from else None,
            "forward_from_chat": str(update.message.forward_from_chat.id) if update.message.forward_from_chat else None,
            "created_at": update.message.date,
            "saved_at": datetime.now(timezone.utc),
        }

        await db.user_notes.insert_one(note_data)

        if is_forwarded:
            response = "**Пересланное сообщение сохранено!**\n\n"
            response += f"**Текст:** {update.message.text[:200]}..."
            response += "\n\n_Сообщение сохранено как заметка без парсинга_"
        else:
            response = "**Сообщение сохранено как заметка!**\n\n"
            response += f"**Текст:** {update.message.text[:200]}..."
            response += "\n\n_Для парсинга объявлений используйте команду /test_"

        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error("Error saving message as note: %s", e)
        await update.message.reply_text("Произошла ошибка при сохранении сообщения. Попробуйте позже.")
