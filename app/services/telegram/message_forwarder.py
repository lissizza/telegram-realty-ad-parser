import logging
import urllib.parse
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from bson import ObjectId
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telethon import functions, types
from telethon.tl.types import Message

from app.core.config import settings
from app.db.mongodb import mongodb
from app.models.incoming_message import IncomingMessage
from app.models.status_enums import IncomingMessageStatus, OutgoingPostStatus
from app.services.user_service import user_service

if TYPE_CHECKING:
    from app.services.telegram.client_manager import TelegramClientManager

logger = logging.getLogger(__name__)


class MessageForwarder:
    """Forwarding, formatting, mark-as-read, channel/topic info utilities."""

    def __init__(self, client_manager: "TelegramClientManager") -> None:
        self.client_manager = client_manager
        self.notification_service: Any = None

    # ------------------------------------------------------------------
    # Mark as read
    # ------------------------------------------------------------------

    async def _mark_message_as_read(self, message: Message) -> None:
        try:
            client = self.client_manager.client
            if not client or not client.is_connected():
                logger.warning("Telegram client not connected, cannot mark message as read")
                return

            try:
                entity = await client.get_entity(message.chat_id)
            except Exception as e:
                logger.warning("Could not get entity for channel %s: %s", message.chat_id, e)
                return

            is_channel = isinstance(entity, (types.Channel, types.ChannelForbidden))

            if is_channel:
                try:
                    await client(functions.channels.ReadHistoryRequest(channel=entity, max_id=message.id))
                    logger.info("Marked message %s as read in channel %s", message.id, message.chat_id)
                except Exception as e:
                    logger.warning("Error marking message %s as read in channel %s: %s", message.id, message.chat_id, e)
            else:
                try:
                    await client(functions.messages.ReadHistoryRequest(peer=entity, max_id=message.id))
                    logger.info("Marked message %s as read in chat %s", message.id, message.chat_id)
                except Exception as e:
                    logger.warning("Error marking message %s as read in chat %s: %s", message.id, message.chat_id, e)

        except Exception as e:
            logger.warning("Error in _mark_message_as_read for message %s: %s", message.id, e)

    # ------------------------------------------------------------------
    # Save message status
    # ------------------------------------------------------------------

    async def _save_message_status(self, message: Message, status: str) -> None:
        try:
            db = mongodb.get_database()
            message_text = message.text or ""

            channel_title = "Unknown Channel"
            try:
                client = self.client_manager.client
                if client:
                    channel = await client.get_entity(message.chat_id)
                    channel_title = getattr(channel, "title", "Unknown Channel")
            except Exception:
                pass

            topic_id = settings.get_topic_id_for_channel(message.chat_id)

            incoming_message = IncomingMessage(
                id=message.id,
                channel_id=message.chat_id,
                topic_id=topic_id,
                channel_title=channel_title,
                message=message_text,
                date=message.date,
                processing_status=status,
                processed_at=datetime.utcnow() if status in ["completed", "failed"] else None,
                parsing_errors=[],
                is_spam=False,
                spam_reason=None,
                is_real_estate=False,
                real_estate_confidence=0.0,
                real_estate_ad_id=None,
                forwarded=False,
                forwarded_at=None,
                forwarded_to=None,
            )

            message_data = incoming_message.model_dump(exclude={"id"})
            await db.incoming_messages.update_one(
                {"id": message.id, "channel_id": message.chat_id}, {"$set": message_data}, upsert=True
            )
            logger.info("Saved message %s with status %s", message.id, status)
        except Exception as e:
            logger.error("Error saving message status: %s", e)

    # ------------------------------------------------------------------
    # Forward post
    # ------------------------------------------------------------------

    async def _forward_post(
        self,
        message: Optional[Message],
        real_estate_ad: Any,
        filter_id: str,
        filter_name: Optional[str] = None,
        target_user_id: Optional[int] = None,
    ) -> None:
        try:
            if target_user_id:
                user_id = target_user_id
                logger.info("Using target_user_id: %s", user_id)
            else:
                user_id = await user_service.get_primary_user_id()
                logger.info("Using primary user_id: %s", user_id)

            if not user_id:
                logger.warning("No user ID found, skipping notification")
                return

            formatted_message = await self._format_real_estate_message(real_estate_ad, message, filter_id, filter_name)

            keyboard = [[InlineKeyboardButton(
                "⚙️ Настроить фильтры",
                web_app=WebAppInfo(url=f"{settings.API_BASE_URL}/api/v1/static/simple-filters?v=1")
            )]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if self.notification_service:
                logger.info("Calling notification_service.send_message for user %s", user_id)
                await self.notification_service.send_message(
                    user_id=user_id, message=formatted_message, parse_mode="MarkdownV2", reply_markup=reply_markup
                )
            else:
                logger.warning("Notification service is not available for user %s", user_id)

            db = mongodb.get_database()

            channel_info = await self._get_channel_info(real_estate_ad.original_channel_id)
            topic_title = None
            if real_estate_ad.original_topic_id:
                topic_title = await self._get_topic_title(real_estate_ad.original_channel_id, real_estate_ad.original_topic_id)

            ad_id = real_estate_ad.id if real_estate_ad.id else None
            if not ad_id:
                existing_ad = await db.real_estate_ads.find_one({"original_post_id": real_estate_ad.original_post_id})
                if existing_ad:
                    ad_id = str(existing_ad["_id"])
                else:
                    logger.error("Cannot forward post: RealEstateAd has no id and not found in database (original_post_id=%s)", real_estate_ad.original_post_id)
                    return

            incoming_message_id = message.id if message else real_estate_ad.original_post_id

            if not ad_id:
                logger.error("Cannot forward post: real_estate_ad_id is required but ad_id is None (user_id=%s, incoming_message_id=%s)", user_id, incoming_message_id)
                return

            if not incoming_message_id:
                logger.error("Cannot forward post: incoming_message_id is required but both message and original_post_id are None (ad_id=%s, user_id=%s)", ad_id, user_id)
                return

            forwarding_data = {
                "message": formatted_message,
                "real_estate_ad_id": ad_id,
                "filter_id": filter_id,
                "user_id": user_id,
                "sent_to": str(user_id),
                "sent_to_type": "user",
                "sent_at": datetime.now(timezone.utc),
                "status": OutgoingPostStatus.SENT.value,
                "channel_id": real_estate_ad.original_channel_id,
                "channel_title": channel_info.get("title") if channel_info else None,
                "topic_id": real_estate_ad.original_topic_id,
                "topic_title": topic_title,
                "incoming_message_id": incoming_message_id,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            try:
                await db.outgoing_posts.insert_one(forwarding_data)
            except Exception as e:
                if "duplicate key error" in str(e).lower() or "E11000" in str(e):
                    logger.warning("Ad %s already sent to user %s for message %s (race condition)", ad_id, user_id, incoming_message_id)
                else:
                    raise

            if message:
                existing_msg = await db.incoming_messages.find_one({"id": message.id, "channel_id": message.chat_id})
                if existing_msg and existing_msg.get("processing_status") != IncomingMessageStatus.DUPLICATE:
                    await db.incoming_messages.update_one(
                        {"id": message.id, "channel_id": message.chat_id},
                        {
                            "$set": {
                                "processing_status": IncomingMessageStatus.FORWARDED,
                                "forwarded": True,
                                "forwarded_at": message.date,
                                "forwarded_to": user_id,
                                "updated_at": message.date,
                            }
                        },
                    )

            logger.info("Forwarded post %s to user %s via filter %s", incoming_message_id, user_id, filter_id)

        except Exception as e:
            logger.error("Error forwarding post: %s", e)

    # ------------------------------------------------------------------
    # Formatting utilities
    # ------------------------------------------------------------------

    def _get_property_type_name(self, property_type: Any) -> str:
        type_names = {
            "apartment": "Квартира",
            "house": "Дом",
            "room": "Комната",
            "hotel_room": "Гостиничный номер",
        }
        return str(type_names.get(property_type, property_type))

    async def _get_filter_name(self, filter_id: str) -> str:
        try:
            logger.info("Getting filter name for ID: %s", filter_id)
            object_id = ObjectId(filter_id)
            db = mongodb.get_database()

            filter_doc = await db.simple_filters.find_one({"_id": object_id})
            if filter_doc:
                return str(filter_doc["name"])

            filter_doc = await db.filters.find_one({"_id": object_id})
            if filter_doc:
                return str(filter_doc["name"])
            else:
                logger.warning("Filter not found for ID: %s", filter_id)
                return f"Фильтр {filter_id[:8]}..."
        except Exception as e:
            logger.error("Error getting filter name: %s", e)
            return f"Фильтр {filter_id[:8]}..."

    def _get_message_link(self, channel_id: int, message_id: int, topic_id: Optional[int] = None) -> str:
        if hasattr(channel_id, "value") and channel_id.value is not None:
            channel_id = channel_id.value
        if hasattr(message_id, "value") and message_id.value is not None:
            message_id = message_id.value
        if topic_id is not None and hasattr(topic_id, "value") and topic_id.value is not None:
            topic_id = topic_id.value

        if topic_id:
            channel_username = settings.TELEGRAM_CHANNEL_USERNAME
            return f"https://t.me/{channel_username}/{topic_id}/{message_id}"

        if channel_id < 0:
            channel_id = abs(channel_id) - 1000000000000
        return f"https://t.me/c/{channel_id}/{message_id}"

    def _escape_markdown(self, text: str) -> str:
        if not text:
            return ""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def _get_yandex_maps_link(self, address: str, district: str = None, city: str = None) -> Optional[str]:
        if not address:
            return None
        try:
            clean_address = address.strip()
            if city and city not in clean_address:
                clean_address = f"{clean_address}, {city}"
            elif not city and "Ереван" not in clean_address and "Yerevan" not in clean_address:
                clean_address = f"{clean_address}, Ереван"

            encoded_address = urllib.parse.quote(clean_address)
            return f"https://yandex.ru/maps/?text={encoded_address}"
        except Exception as e:
            logger.error("Error generating Yandex Maps link for address '%s': %s", address, e)
            return None

    async def _format_real_estate_message(
        self, real_estate_ad: Any, _original_message: Optional[Message], filter_id: Optional[str] = None, filter_name: Optional[str] = None
    ) -> str:
        channel_info = await self._get_channel_info(real_estate_ad.original_channel_id)
        channel_title = "Неизвестного канала"
        channel_link = ""

        if channel_info:
            channel_title = self._escape_markdown(channel_info.get('title', 'Неизвестного канала'))
            if channel_info.get('username'):
                username = channel_info['username'].lstrip('@')
                channel_link = f" \\(@{self._escape_markdown(username)}\\)"

        message = f"🏠 *Найдено подходящее объявление из канала {channel_title}{channel_link}\\!*\n\n"

        if real_estate_ad.property_type:
            property_name = self._get_property_type_name(real_estate_ad.property_type)
            message += f"*Тип:* {self._escape_markdown(property_name)}\n"
        if real_estate_ad.rooms_count:
            message += f"*Комнат:* {self._escape_markdown(str(real_estate_ad.rooms_count))}\n"
        if real_estate_ad.area_sqm:
            message += f"*Площадь:* {self._escape_markdown(str(real_estate_ad.area_sqm))} кв\\.м\n"
        if real_estate_ad.floor is not None:
            if real_estate_ad.total_floors is not None:
                message += f"*Этаж:* {self._escape_markdown(str(real_estate_ad.floor))}/{self._escape_markdown(str(real_estate_ad.total_floors))}\n"
            else:
                message += f"*Этаж:* {self._escape_markdown(str(real_estate_ad.floor))}\n"
        if real_estate_ad.price:
            currency_value = real_estate_ad.currency.value if hasattr(real_estate_ad.currency, 'value') else str(real_estate_ad.currency)
            currency_symbol = "драм" if currency_value == "AMD" else currency_value
            message += f"*Цена:* {self._escape_markdown(f'{real_estate_ad.price:,} {currency_symbol}')}\n"
        if real_estate_ad.district:
            message += f"*Район:* {self._escape_markdown(real_estate_ad.district)}\n"
        if real_estate_ad.city:
            message += f"*Город:* {self._escape_markdown(real_estate_ad.city)}\n"
        if real_estate_ad.address:
            yandex_maps_link = self._get_yandex_maps_link(real_estate_ad.address, real_estate_ad.district, real_estate_ad.city)
            if yandex_maps_link:
                message += f"*Адрес:* [{self._escape_markdown(real_estate_ad.address)}]({yandex_maps_link})\n"
                message += f"🗺️ [Посмотреть на карте]({yandex_maps_link})\n"
            else:
                message += f"*Адрес:* {self._escape_markdown(real_estate_ad.address)}\n"
        if real_estate_ad.contacts:
            contacts_str = (
                ", ".join(real_estate_ad.contacts)
                if isinstance(real_estate_ad.contacts, list)
                else str(real_estate_ad.contacts)
            )
            message += f"*Контакты:* {self._escape_markdown(contacts_str)}\n"

        channel_info = await self._get_channel_info(real_estate_ad.original_channel_id)
        if channel_info:
            ch_title = self._escape_markdown(channel_info.get('title', 'Неизвестный канал'))
            message += f"\n*📢 Канал:* {ch_title}"
            if channel_info.get('username'):
                username = channel_info['username'].lstrip('@')
                escaped_username = username.replace('_', '\\_')
                message += f" \\(@{escaped_username}\\)"

            if real_estate_ad.original_topic_id:
                topic_title = await self._get_topic_title(real_estate_ad.original_channel_id, real_estate_ad.original_topic_id)
                if topic_title:
                    message += f"\n*📌 Топик:* {self._escape_markdown(topic_title)}"
                else:
                    message += f"\n*📌 Топик:* #{real_estate_ad.original_topic_id}"

        if filter_name:
            message += f"\n*🎯 Активный фильтр:* {self._escape_markdown(filter_name)}\n"
        elif filter_id and filter_id != "unknown":
            fname = await self._get_filter_name(str(filter_id))
            message += f"\n*🎯 Активный фильтр:* {self._escape_markdown(fname)}\n"

        message += f"\n*Уверенность:* {self._escape_markdown(f'{real_estate_ad.parsing_confidence:.2f}')}\n"

        if _original_message:
            message_link = self._get_message_link(
                _original_message.chat_id, _original_message.id, real_estate_ad.original_topic_id
            )
        else:
            message_link = self._get_message_link(
                real_estate_ad.original_channel_id, real_estate_ad.original_post_id, real_estate_ad.original_topic_id
            )

        original_text = self._escape_markdown(real_estate_ad.original_message[:300])
        message += f"\n*Оригинальный текст:*\n{original_text}\\.\\.\\.\n\n"
        message += f"🔗 [Читать полностью]({message_link})"

        return message

    # ------------------------------------------------------------------
    # Channel / topic info (needs Telegram client)
    # ------------------------------------------------------------------

    async def _get_channel_info(self, channel_id: int) -> Optional[Dict[str, str]]:
        try:
            client = self.client_manager.client
            if not client:
                return None
            if channel_id < 0:
                regular_id = abs(channel_id) - 1000000000000
            else:
                regular_id = channel_id

            entity = await client.get_entity(regular_id)
            return {
                'id': channel_id,
                'title': getattr(entity, 'title', 'Неизвестный канал'),
                'username': getattr(entity, 'username', None)
            }
        except Exception as e:
            logger.error("Error getting channel info for %s: %s", channel_id, e)
            return None

    async def _get_topic_title(self, channel_id: int, topic_id: int) -> Optional[str]:
        try:
            client = self.client_manager.client
            if not client:
                return None
            if channel_id < 0:
                regular_id = abs(channel_id) - 1000000000000
            else:
                regular_id = channel_id

            channel = await client.get_input_entity(regular_id)
            result = await client(functions.channels.GetForumTopicsByIDRequest(
                channel=channel, topics=[topic_id]
            ))
            if result.topics:
                return result.topics[0].title
            return None
        except Exception as e:
            logger.error("Error getting topic title for channel %s, topic %s: %s", channel_id, topic_id, e)
            return None
