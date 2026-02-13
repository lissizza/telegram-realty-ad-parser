import logging
from typing import TYPE_CHECKING, List

from telethon.tl.types import Message

from app.core.config import settings

if TYPE_CHECKING:
    from app.services.telegram.client_manager import TelegramClientManager

logger = logging.getLogger(__name__)


class MessageValidator:
    """Topic checks, bot/media filtering, channel lookup."""

    def __init__(self, client_manager: "TelegramClientManager") -> None:
        self.client_manager = client_manager

    # ------------------------------------------------------------------
    # Legacy channel helpers
    # ------------------------------------------------------------------

    def _get_monitored_channels_legacy(self) -> List[int]:
        try:
            channel_strings = settings.monitored_channels_list
            if not channel_strings:
                logger.warning("No monitored channels configured")
                return []

            channel_ids: list = []
            for channel_id in channel_strings:
                channel_id = channel_id.strip()
                if not channel_id:
                    continue
                try:
                    if channel_id.startswith("@"):
                        channel_ids.append(channel_id)
                    else:
                        channel_ids.append(int(channel_id))
                except ValueError as e:
                    logger.warning("Invalid channel ID format: %s - %s", channel_id, e)
                    continue

            if not channel_ids:
                logger.warning("No valid monitored channels found")
                return []

            logger.info("Monitoring %s channels (legacy): %s", len(channel_ids), channel_ids)
            return channel_ids
        except Exception as e:
            logger.error("Error getting monitored channels: %s", e)
            return []

    def _get_monitored_subchannels(self) -> List[tuple]:
        try:
            subchannels = settings.monitored_subchannels_list
            return subchannels if subchannels else []
        except Exception as e:
            logger.error("Error getting monitored subchannels: %s", e)
            return []

    # ------------------------------------------------------------------
    # Message validation
    # ------------------------------------------------------------------

    def _is_message_in_topic_correct(self, message: Message) -> bool:
        try:
            rt = getattr(message, "reply_to", None)
            if rt:
                return False
            return True
        except Exception as e:
            logger.error("Error checking topic: %s", e)
            return False

    async def _is_from_monitored_subchannel(self, message: Message) -> bool:
        try:
            channel_id = message.chat_id
            monitored_subchannels = self._get_monitored_subchannels()

            if not monitored_subchannels:
                return True

            excluded_subchannels = []
            if settings.TELEGRAM_EXCLUDED_SUBCHANNELS:
                try:
                    excluded_subchannels = [int(x.strip()) for x in settings.TELEGRAM_EXCLUDED_SUBCHANNELS.split(",") if x.strip()]
                except ValueError as e:
                    logger.warning("Invalid excluded subchannels format: %s", e)

            for monitored_channel_id, topic_id in monitored_subchannels:
                if monitored_channel_id == channel_id:
                    is_in_topic = await self.client_manager._is_message_in_topic(message, channel_id, topic_id)
                    if is_in_topic:
                        if topic_id not in excluded_subchannels:
                            logger.info("Processing message %s from channel %s, subchannel %s", message.id, channel_id, topic_id)
                            return True
                        else:
                            logger.debug("Message %s is in excluded subchannel %s:%s, skipping", message.id, channel_id, topic_id)
                            return False

            channel_in_monitored = any(mid == channel_id for mid, _ in monitored_subchannels)
            if channel_in_monitored:
                logger.debug("Message %s from channel %s is not in any monitored subchannel, skipping", message.id, channel_id)
                return False

            logger.debug("Message %s from channel %s - subchannels not configured for this channel, processing", message.id, channel_id)
            return True
        except Exception as e:
            logger.error("Error checking subchannel: %s", e)
            return False

    def _is_technical_bot_message(self, message_text: str) -> bool:
        if not message_text:
            return False

        tech_indicators = [
            "недостаточно прав",
            "блокировки",
            "тихий режим",
            "настройки бота",
            "технические особенности",
            "работать некорректно",
            "cas.chat",
            "заблокировали",
            "lolsbot",
            "antispam",
            "антиспам",
            "спам",
            "botcatcher",
            "бесплатный антиспам",
            "usdt за наличные",
            "курс честный",
            "безопасная встреча",
            "билеты",
        ]

        return any(tech_indicator in message_text.lower() for tech_indicator in tech_indicators)

    def _is_media_only_message(self, message: Message) -> bool:
        try:
            if message.text and message.text.strip():
                return False

            has_media = (
                message.photo
                or message.video
                or message.document
                or message.audio
                or message.voice
                or message.video_note
                or message.sticker
                or getattr(message, "animation", None)
                or message.contact
                or message.location
                or message.venue
                or message.poll
                or getattr(message, "game", None)
                or getattr(message, "web_preview", None)
            )

            return bool(has_media)
        except Exception as e:
            logger.error("Error checking media-only message: %s", e)
            return False
