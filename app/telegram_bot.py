"""
Telegram bot orchestrator — sets up handlers and manages lifecycle.

All handler logic lives in app/bot/ submodules.
"""

import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.core.config import settings
from app.bot.command_handlers import (
    start_command, help_command, settings_command,
    stats_command, myid_command, users_command,
)
from app.bot.llm_handlers import test_command, analyze_command
from app.bot.processing_handlers import reprocess_command, refilter_command
from app.bot.callback_handlers import handle_callback
from app.bot.message_handlers import handle_message
from app.bot.admin_commands import (
    admin_panel, promote_user, demote_user, create_super_admin,
)

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot — orchestrator only."""

    def __init__(self):
        self.application = None
        self.bot_token = settings.TELEGRAM_BOT_TOKEN

    def setup_handlers(self):
        """Register all command, message, and callback handlers."""
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("help", help_command))
        self.application.add_handler(CommandHandler("settings", settings_command))
        self.application.add_handler(CommandHandler("stats", stats_command))
        self.application.add_handler(CommandHandler("test", test_command))
        self.application.add_handler(CommandHandler("reprocess", reprocess_command))
        self.application.add_handler(CommandHandler("refilter", refilter_command))
        self.application.add_handler(CommandHandler("analyze", analyze_command))

        # Admin commands
        self.application.add_handler(CommandHandler("admin", admin_panel))
        self.application.add_handler(CommandHandler("promote", promote_user))
        self.application.add_handler(CommandHandler("demote", demote_user))
        self.application.add_handler(CommandHandler("create_super_admin", create_super_admin))

        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        self.application.add_handler(CallbackQueryHandler(handle_callback))

    async def setup_commands_menu(self):
        """Setup bot commands menu visible in Telegram UI."""
        commands = [
            BotCommand("start", "Главное меню"),
            BotCommand("help", "Справка"),
            BotCommand("settings", "Настройки поиска"),
            BotCommand("stats", "Статистика"),
            BotCommand("test", "Парсинг объявления (LLM)"),
        ]
        await self.application.bot.set_my_commands(commands)
        logger.info("Bot commands menu set up successfully")

    async def start_bot(self):
        """Start the bot."""
        try:
            if not self.bot_token:
                raise ValueError("Bot token is not configured")
            logger.info(
                "Initializing Telegram bot with token: %s...",
                self.bot_token[:10] if self.bot_token else "None",
            )
            self.application = Application.builder().token(self.bot_token).build()
            self.setup_handlers()

            logger.info("Starting Telegram bot...")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()

            await self.setup_commands_menu()

            logger.info("Telegram bot started successfully")
        except Exception as e:
            logger.error("Failed to start Telegram bot: %s", e)
            logger.error(
                "Bot token: %s...",
                self.bot_token[:10] if self.bot_token else "None",
            )
            raise

    async def stop_bot(self):
        """Stop the bot."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram bot stopped")


# Global bot instance
telegram_bot = TelegramBot()
