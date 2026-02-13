"""LLM-related command handlers: /test, /analyze"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.db.mongodb import mongodb
from app.services import get_telegram_service
from app.services.llm_service import LLMService
from app.services.monitored_channel_service import MonitoredChannelService

logger = logging.getLogger(__name__)


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /test command - parse real estate ad with LLM"""
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text(
            "Использование: /test <текст объявления>\n\n"
            "Пример: /test Сдаю 3-комнатную квартиру в центре Еревана, 250000 драм\n\n"
            "*Внимание: Использование LLM парсинга платное*"
        )
        return

    test_text = " ".join(context.args)
    await update.message.reply_text("🧪 Парсинг объявления с помощью LLM...")

    try:
        llm_service = LLMService()
        real_estate_ad = await llm_service.parse_with_llm(
            test_text, update.message.message_id, update.message.chat_id
        )

        if not real_estate_ad:
            await update.message.reply_text(
                "Не удалось распознать объявление о недвижимости. "
                "Попробуйте отправить более подробное описание."
            )
            return

        db = mongodb.get_database()
        ad_data = real_estate_ad.dict(exclude={"id"})
        result = await db.real_estate_ads.insert_one(ad_data)
        real_estate_ad.id = str(result.inserted_id)

        response = "**Объявление обработано!**\n\n"
        response += f"**Тип:** {real_estate_ad.property_type}\n"
        response += f"**Комнат:** {real_estate_ad.rooms_count}\n"
        response += f"**Площадь:** {real_estate_ad.area_sqm} кв.м\n"
        if real_estate_ad.floor is not None:
            if real_estate_ad.total_floors is not None:
                response += f"**Этаж:** {real_estate_ad.floor}/{real_estate_ad.total_floors}\n"
            else:
                response += f"**Этаж:** {real_estate_ad.floor}\n"
        response += f"**Цена:** {real_estate_ad.price} {real_estate_ad.currency}\n"
        response += f"**Район:** {real_estate_ad.district}\n"
        response += f"**Уверенность:** {real_estate_ad.parsing_confidence:.2f}\n\n"
        response += f"**Текст:** {test_text[:200]}..."

        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error("Error parsing with LLM: %s", e)
        await update.message.reply_text("Произошла ошибка при парсинге. Попробуйте позже.")


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /analyze command"""
    if not update.message:
        return
    try:
        message = update.message

        limit = 50
        if context.args and len(context.args) >= 1:
            try:
                limit = int(context.args[0])
                if limit <= 0 or limit > 200:
                    await message.reply_text("Количество сообщений должно быть от 1 до 200")
                    return
            except ValueError:
                await message.reply_text("Неверный формат. Используйте: /analyze [количество]")
                return

        await message.reply_text(
            f"Анализирую структуру канала (последние {limit} сообщений)...\n"
            "Это может занять некоторое время..."
        )

        telegram_service = get_telegram_service()
        if not telegram_service:
            await message.reply_text("Сервис обработки сообщений недоступен")
            return

        svc = MonitoredChannelService()
        active_channels = await svc.get_active_channels()
        if not active_channels:
            await message.reply_text("Нет настроенных каналов для анализа")
            return

        channel_id = int(active_channels[0].channel_id)
        result = await telegram_service.analyze_channel_structure(channel_id, limit)

        if result:
            response = f"**Анализ канала {channel_id}**\n\n"
            response += "**Статистика:**\n"
            response += f"• Сообщений без топика (основной канал): {result['no_topic_count']}\n"
            response += f"• Всего топиков: {len(result['topic_stats'])}\n\n"

            if result["topic_stats"]:
                response += "**Топики:**\n"
                for topic_id, count in result["topic_stats"].items():
                    response += f"• Топик {topic_id}: {count} сообщений\n"

            response += "\n**Примеры сообщений:**\n"
            for i, msg in enumerate(result["sample_messages"][:5], 1):
                response += f"\n**{i}.** ID: {msg['id']}\n"
                response += f"Текст: {msg['text']}...\n"
                response += f"Reply to: {msg['reply_to']}\n"
                response += f"Reply to top ID: {msg['reply_to_top_id']}\n"
                response += f"Дата: {msg['date']}\n"

            await message.reply_text(response)
        else:
            await message.reply_text("Ошибка при анализе канала")

    except Exception as e:
        logger.error("Error in analyze command: %s", e)
        await message.reply_text(f"Произошла ошибка: {str(e)}")
