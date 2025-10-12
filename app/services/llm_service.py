"""
LLM Service for real estate ad parsing.

This module provides functionality to parse real estate advertisements using
various LLM providers (OpenAI, Anthropic, local models) and extract structured
information from unstructured text.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

import asyncio
import httpx
from anthropic import AsyncAnthropic, RateLimitError as AnthropicRateLimitError
from openai import AsyncOpenAI, RateLimitError as OpenAIRateLimitError, APIError as OpenAIAPIError

from app.core.config import settings
from app.db.mongodb import mongodb
from app.exceptions import LLMQuotaExceededError
from app.models.llm_cost import LLMCost
from app.models.telegram import PropertyType, RealEstateAd, RentalType
from app.services.admin_notification_service import admin_notification_service

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM-based real estate ad parsing with multiple providers"""

    def __init__(self) -> None:
        self.provider = str(settings.LLM_PROVIDER).lower()
        self.model = str(settings.LLM_MODEL)
        self.api_key = str(settings.LLM_API_KEY)
        self.base_url = settings.LLM_BASE_URL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE

        # Initialize client based on provider
        self.client: Optional[Any] = None
        if self.provider == "openai":
            self.client = AsyncOpenAI(api_key=self.api_key)
        elif self.provider == "anthropic":
            self.client = AsyncAnthropic(api_key=self.api_key)
        elif self.provider == "local":
            # For local models (Ollama, etc.)
            self.client = None  # Will use httpx directly
        elif self.provider == "mock":
            self.client = None  # Mock implementation

        # LLM pricing (per 1K tokens)
        self.pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        }

    async def parse_with_llm(
        self,
        text: str,
        post_id: int,
        channel_id: int,
        incoming_message_id: Optional[str] = None,
        topic_id: Optional[int] = None,
    ) -> Optional[RealEstateAd]:
        """Parse real estate ad using LLM"""
        try:
            # Create parsing prompt
            prompt = self._create_parsing_prompt(text)

            # Call LLM (may raise exception for quota errors)
            llm_result = await self._call_llm(prompt)
            if not llm_result:
                return None

            llm_response = llm_result["response"]
            cost_info = llm_result["cost_info"]

            # Save cost information
            await self._save_llm_cost(post_id, channel_id, cost_info)

            # Parse LLM response
            parsed_data = self._parse_llm_response(llm_response)

            if not parsed_data:
                return None

            # Create RealEstateAd object
            ad = RealEstateAd(
                incoming_message_id=incoming_message_id,
                original_post_id=post_id,
                original_channel_id=channel_id,
                original_topic_id=topic_id,
                original_message=text,
                processing_status="completed",
                llm_processed=True,
                llm_cost=cost_info.get("cost_usd"),
                **parsed_data,
            )
            
            # Copy rooms_count to rooms for API compatibility
            if ad.rooms_count is not None:
                ad.rooms = ad.rooms_count

            # Save to database (all LLM results are saved)
            await self._save_real_estate_ad(ad)

            return ad

        except (OpenAIRateLimitError, AnthropicRateLimitError) as e:
            # LLM quota/rate limit exceeded (both providers)
            provider = "openai" if isinstance(e, OpenAIRateLimitError) else "anthropic"
            logger.error("LLM quota exceeded while parsing message %s (provider: %s): %s", post_id, provider, e)
            
            # Notify super admins
            try:
                asyncio.create_task(admin_notification_service.notify_quota_exceeded(str(e)))
            except Exception as notify_error:
                logger.error("Error creating notification task: %s", notify_error)
            
            # Raise custom exception to be handled by caller
            raise LLMQuotaExceededError(str(e), provider=provider, original_error=e)
        except (OpenAIAPIError, Exception) as e:
            # Other errors (API errors, parsing errors, etc.)
            logger.error("Error parsing with LLM: %s", e)
            return None

    def _create_parsing_prompt(self, text: str) -> str:
        """Create prompt for LLM parsing"""
        return f"""You are a real estate listing parser for Russian Telegram posts.
Extract structured information into JSON format.

INSTRUCTIONS:
1. Analyze if message is genuine real estate listing OFFERING property for rent/sale
2. Messages about SEARCHING for property should be marked as is_real_estate: false
3. Extract all available parameters using context clues
4. Handle language variations and informal writing
5. Use null for missing data, don't guess
6. Return confidence score based on extraction certainty

IMPORTANT CLASSIFICATION RULES:
- OFFER messages: "сдаю", "сдам", "продаю", "предлагаю", "сдается", "продается" = REAL ESTATE
- SEARCH messages: "ищу", "сниму", "нужна", "требуется", "ищем", "нужен" = NOT REAL ESTATE
- If message is about finding/buying/renting property, mark is_real_estate: false
- Only messages offering property for rent/sale should be marked as real estate

RUSSIAN TERMS:
Rent: сдаю, сдам, сдается, аренда, снять, в аренду
Sale: продаю, продам, продается, купить, продажа
Want rent: сниму, ищу, нужна, требуется
Apartment: квартира, кв, квартиру
Room: комната, ком, комнату
House: дом, коттедж, таунхаус
Studio: студия, однушка
Commercial: офис, магазин, склад
Room counts: 1к, 1-к, однокомнатная, однушка, студия, 2к, 2-к, двухкомнатная, двушка, 3к, трешка, 4к
Floor info: X/Y этаж, X/Y этаж, на X этаже, X-й этаж (X = current floor, Y = total floors)
Long-term: долгосрочно, долгосрок, на длительный срок
Short-term: посуточно, на сутки, краткосрок, суточно

IMPORTANT:
- "3/8 этаж" means floor 3 of 8 total floors, NOT 3 rooms
- "X/Y этаж" format is ALWAYS about floors, never rooms
- STUDIO APARTMENTS: "студия", "квартира-студия", "однушка" ALWAYS means 1 room
- Count rooms when explicitly mentioned: "2к", "двушка", "3 комнаты", "студия", etc.
- If only floor info is given without room count, set rooms_count to null
- Studio apartments are 1-room apartments, not separate room type

JSON STRUCTURE:
{{
  "is_real_estate": boolean,
  "parsing_confidence": number (0.0-1.0),
  "property_type": string ("apartment"/"room"/"house"/"hotel_room"/null),
  "rental_type": string ("long_term"/"daily"/null),
  "rooms_count": number (null if unknown),
  "area_sqm": number (null if unknown),
  "price": number (null if unknown),
  "currency": string ("AMD"/"USD"/"RUB"/"EUR"/"GBP"/null),
  "city": string (null if unknown),
  "district": string (null if unknown),
  "address": string (null if unknown),
  "contacts": array of strings (null if unknown),
  "has_balcony": boolean (null if unknown),
  "has_air_conditioning": boolean (null if unknown),
  "has_internet": boolean (null if unknown),
  "has_furniture": boolean (null if unknown),
  "has_parking": boolean (null if unknown),
  "has_garden": boolean (null if unknown),
  "has_pool": boolean (null if unknown),
  "has_elevator": boolean (null if unknown),
  "pets_allowed": boolean (null if unknown),
  "utilities_included": boolean (null if unknown),
  "floor": number (null if unknown),
  "total_floors": number (null if unknown),
  "additional_notes": string (null if unknown)
}}

EXAMPLES:

Example 1 (with room count):
Input: "Сдаю 2к квартиру, 5/9 этаж, 55кв.м, Москва, район Измайлово, 45000₽/мес, мебель, без животных"
Output:
{{
  "is_real_estate": true,
  "parsing_confidence": 0.95,
  "property_type": "apartment",
  "rental_type": "long_term",
  "rooms_count": 2,
  "area_sqm": 55,
  "price": 45000,
  "currency": "RUB",
  "district": "Измайлово",
  "address": null,
  "contacts": null,
  "has_balcony": null,
  "has_air_conditioning": null,
  "has_internet": null,
  "has_furniture": true,
  "has_parking": null,
  "has_garden": null,
  "has_pool": null,
  "has_elevator": null,
  "pets_allowed": false,
  "utilities_included": null,
  "floor": 5,
  "total_floors": 9,
  "city": "Москва",
  "additional_notes": null
}}

Example 2 (floor info only, no room count):
Input: "Рубен Севака 26, 3/8 этаж, 500.000драм, Без комиссии"
Output:
{{
  "is_real_estate": true,
  "parsing_confidence": 0.8,
  "property_type": "apartment",
  "rental_type": "long_term",
  "rooms_count": null,
  "area_sqm": null,
  "price": 500000,
  "currency": "AMD",
  "district": null,
  "address": "Рубен Севака 26",
  "contacts": null,
  "has_balcony": null,
  "has_air_conditioning": null,
  "has_internet": null,
  "has_furniture": null,
  "has_parking": null,
  "has_garden": null,
  "has_pool": null,
  "has_elevator": null,
  "pets_allowed": null,
  "utilities_included": null,
  "floor": 3,
  "total_floors": 8,
  "city": null,
  "additional_notes": "Only floor information provided (3/8), no room count mentioned"
}}

Example 3 (Yerevan address parsing):
Input: "Адрес: Маштоц, Кентрон, Ереван"
Output:
{{
  "is_real_estate": true,
  "parsing_confidence": 0.9,
  "property_type": "apartment",
  "rental_type": "long_term",
  "rooms_count": null,
  "area_sqm": null,
  "price": null,
  "currency": null,
  "district": "Кентрон",
  "address": "улица Маштоца",
  "contacts": null,
  "has_balcony": null,
  "has_air_conditioning": null,
  "has_internet": null,
  "has_furniture": null,
  "has_parking": null,
  "has_garden": null,
  "has_pool": null,
  "has_elevator": null,
  "pets_allowed": null,
  "utilities_included": null,
  "floor": null,
  "total_floors": null,
  "city": "Ереван",
  "additional_notes": null
}}

Example 4 (Studio apartment - 1 room):
Input: "Сдается квартира-студия в новом апартаментном комплексе в Арабкире. Адрес: улица Керу 17. Цена: 170 000 ֏ в месяц (плюс коммунальные услуги). Площадь: 25 кв. м."
Output:
{{
  "is_real_estate": true,
  "parsing_confidence": 0.95,
  "property_type": "apartment",
  "rental_type": "long_term",
  "rooms_count": 1,
  "area_sqm": 25,
  "price": 170000,
  "currency": "AMD",
  "district": "Арабкир",
  "address": "улица Керу 17",
  "contacts": null,
  "has_balcony": null,
  "has_air_conditioning": null,
  "has_internet": null,
  "has_furniture": null,
  "has_parking": null,
  "has_garden": null,
  "has_pool": null,
  "has_elevator": null,
  "pets_allowed": null,
  "utilities_included": false,
  "floor": null,
  "total_floors": null,
  "city": "Ереван",
  "additional_notes": "Studio apartment is treated as 1-room apartment"
}}

Example 5 (SEARCH message - should be false):
Input: "Здравствуйте. Ищем квартиру, бюджет до 150 000. Для молодой пары. Хорошая транспортная развязка. Желательно Ереван, но можно Абовян. По возможности без предоплаты и комиссий."
Output:
{{
  "is_real_estate": false,
  "parsing_confidence": 0.0,
  "property_type": null,
  "rental_type": null,
  "rooms_count": null,
  "area_sqm": null,
  "price": null,
  "currency": null,
  "city": null,
  "district": null,
  "address": null,
  "contacts": null,
  "has_balcony": null,
  "has_air_conditioning": null,
  "has_internet": null,
  "has_furniture": null,
  "has_parking": null,
  "has_garden": null,
  "has_pool": null,
  "has_elevator": null,
  "pets_allowed": null,
  "utilities_included": null,
  "floor": null,
  "total_floors": null,
  "additional_notes": "This is a search request, not an offer. Person is looking for an apartment to rent."
}}

EXTRACTION RULES:
- If information is not available, use null
- For boolean fields, use true/false
- For arrays, use empty array [] if no data
- Extract phone numbers with country code if available, otherwise add appropriate country code based
 on city/address context
- Extract Telegram usernames as @username
- For districts, use standard Yerevan district names (Кентрон, Арабкир, Аван, Нор-Норк, Эребуни, Шенгавит, Давидашен, Ачапняк, Норк-Мараш, Канакер-Зейтун, Малатия-Себастия, Норк-Мараш)
- For city, extract main city name (Ереван, Москва, Санкт-Петербург, etc.)
- For address, extract street names, building numbers, metro stations
- IMPORTANT: For Yerevan addresses, parse format "улица, район, город" correctly:
  * "Маштоц, Кентрон, Ереван" = address: "улица Маштоца", district: "Кентрон", city: "Ереван"
  * "Абовяна 15, Кентрон, Ереван" = address: "улица Абовяна 15", district: "Кентрон", city: "Ереван"
  * "Туманяна 25, Арабкир, Ереван" = address: "улица Туманяна 25", district: "Арабкир", city: "Ереван"

NOTES:
- Mark is_real_estate false for spam, jobs, services
- Extract prices with currency symbols or words like рублей, тысяч, драм, долларов, евро, фунтов
- Recognize metro stations and street names in addresses
- Lower confidence for ambiguous listings
- Handle creative abbreviations and informal language
- For ambiguous or unclear information, document your reasoning in additional_notes
- If multiple prices are mentioned (e.g., monthly vs yearly), choose the most relevant one and note the ambiguity
 in additional_notes
- If room count is unclear or could be interpreted differently, explain in additional_notes
- For any parsing decisions that might be controversial, add explanation to additional_notes
- ADDRESS PARSING: For Yerevan addresses, always parse "улица, район, город" format correctly:
  * First part = street name (add "улица" prefix if not present)
  * Second part = district (use standard district names)
  * Third part = city (usually "Ереван")
  * Example: "Маштоц, Кентрон, Ереван" → address: "улица Маштоца", district: "Кентрон", city: "Ереван"

Analyze this real estate text and return JSON:

{text}"""

    async def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call LLM API based on provider - may raise RateLimitError"""
        if self.provider == "openai":
            return await self._call_openai(prompt)
        if self.provider == "anthropic":
            return await self._call_anthropic(prompt)
        if self.provider == "local":
            return await self._call_local(prompt)
        if self.provider == "mock":
            return await self._call_mock(prompt)
        logger.error("Unknown LLM provider: %s", self.provider)
        return None

    async def _call_openai(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call OpenAI API - raises exceptions on errors"""
        if not self.client or not hasattr(self.client, "chat"):
            logger.error("OpenAI client not properly initialized")
            return None

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing real estate advertisements "
                    "in Armenian and Russian languages.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        content = response.choices[0].message.content
        usage = response.usage

        if not usage:
            logger.error("No usage information in OpenAI response")
            return None

        return {
            "response": content,
            "cost_info": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cost_usd": self._calculate_cost(usage.prompt_tokens, usage.completion_tokens),
                "model_name": self.model,
            },
        }

    async def _call_anthropic(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call Anthropic API - raises exceptions on errors"""
        if not self.client or not hasattr(self.client, "messages"):
            logger.error("Anthropic client not properly initialized")
            return None

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        usage = response.usage

        if not usage:
            logger.error("No usage information in Anthropic response")
            return None

        return {
            "response": content,
            "cost_info": {
                "prompt_tokens": usage.input_tokens,
                "completion_tokens": usage.output_tokens,
                "total_tokens": usage.input_tokens + usage.output_tokens,
                "cost_usd": self._calculate_cost(usage.input_tokens, usage.output_tokens),
                "model_name": self.model,
            },
        }

    async def _call_local(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call local LLM API (Ollama, etc.)"""
        try:
            if not self.base_url:
                logger.error("LLM_BASE_URL not configured for local provider")
                return None

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an expert at analyzing real estate advertisements "
                                "in Armenian and Russian languages.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": self.max_tokens,
                        "temperature": self.temperature,
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()

                content = data["choices"][0]["message"]["content"]
                usage = data["usage"]

                return {
                    "response": content,
                    "cost_info": {
                        "prompt_tokens": usage["prompt_tokens"],
                        "completion_tokens": usage["completion_tokens"],
                        "total_tokens": usage["total_tokens"],
                        "cost_usd": 0.0,  # Local models are free
                        "model_name": self.model,
                    },
                }
        except Exception as e:
            logger.error("Error calling local LLM: %s", e)
            return None

    async def _call_mock(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Mock LLM implementation for testing"""
        # Extract text from prompt
        if "Text:" in prompt:
            text = prompt.split("Text:")[-1].strip()
            if "{" in text:
                text = text.split("{")[0].strip()
        else:
            text = ""

        text_lower = text.lower()

        # Check if it's likely spam or non-real-estate
        spam_indicators = [
            "билет",
            "ticket",
            "концерт",
            "standup",
            "спам",
            "реклама",
            "крипто",
            "заработок",
            "мероприятие",
            "event",
            "gastro",
            "tour",
        ]
        if any(indicator in text_lower for indicator in spam_indicators):
            response = json.dumps(
                {"is_real_estate": False, "reason": "Contains spam indicators or non-real-estate content"},
                ensure_ascii=False,
            )
        else:
            # Check for search messages (people looking for property)
            search_indicators = [
                "ищу",
                "ищем",
                "сниму",
                "нужна",
                "нужен",
                "требуется",
                "ищется",
                "ищут",
                "нужны",
                "требуются",
                "разыскиваю",
                "разыскиваем",
                "ищу квартиру",
                "ищу дом",
                "ищу комнату",
                "нужна квартира",
                "нужен дом",
                "нужна комната",
                "требуется квартира",
                "требуется дом",
                "требуется комната",
            ]

            is_search_message = any(indicator in text_lower for indicator in search_indicators)

            if is_search_message:
                response = json.dumps(
                    {
                        "is_real_estate": False,
                        "reason": "This is a search request, not an offer. Person is looking for property to rent/buy."
                    },
                    ensure_ascii=False,
                )
            else:
                # Check for real estate context (offers)
                real_estate_indicators = [
                    "сдаю",
                    "сдаётся",
                    "сдается",
                    "сдам",
                    "сдаём",
                    "аренд",
                    "аренда",
                    "аренду",
                    "предлагаю",
                    "предлагаем",
                    "предлагает",
                    "предложение",
                    "квартир",
                    "дом",
                    "комнат",
                    "жилье",
                    "недвижимость",
                    "апартамент",
                    "кв.м",
                    "кв м",
                    "квадрат",
                    "площадь",
                    "этаж",
                    "этажей",
                    "подъезд",
                    "балкон",
                    "лоджия",
                    "кухня",
                    "ванная",
                    "туалет",
                    "коридор",
                    "мебель",
                    "меблирован",
                    "ремонт",
                    "новостройка",
                    "современный",
                    "цена",
                    "стоимость",
                    "драм",
                    "доллар",
                    "usd",
                    "$",
                    "₽",
                    "руб",
                    "свяжитесь",
                    "пишите",
                    "звоните",
                    "телефон",
                    "контакт",
                    "ереван",
                    "центр",
                    "кентрон",
                    "арабкир",
                    "малатия",
                    "эребуни",
                    "шахумян",
                    "канакер",
                    "аван",
                    "нор-норк",
                    "шенгавит",
                ]

                indicator_count = sum(1 for indicator in real_estate_indicators if indicator in text_lower)

                # Check for price patterns
                price_patterns = [
                    r"\d+\s*000?\s*драм",
                    r"\d+\s*000?\s*₽",
                    r"\$\d+",
                    r"\d+\s*доллар",
                    r"\d+\s*usd",
                    r"\d+\s*к\s*драм",
                ]
                has_price = any(re.search(pattern, text_lower) for pattern in price_patterns)

                # Check for numeric values
                has_numbers = bool(re.search(r"\d+", text))

                # Determine if it's real estate offer
                is_real_estate_offer = (
                    indicator_count >= 1
                    or (has_price and has_numbers)
                    or (has_numbers and "квартир" in text_lower)
                    or (has_numbers and "комнат" in text_lower)
                    or (has_numbers and "дом" in text_lower)
                    or ("сдаётся" in text_lower)
                    or ("сдается" in text_lower)
                    or ("сдаю" in text_lower)
                    or ("сдам" in text_lower)
                    or ("сдаём" in text_lower)
                )

                if is_real_estate_offer:
                    # Simulate real estate ad parsing
                    response = json.dumps(
                        {
                            "is_real_estate": True,
                            "property_type": "apartment",
                            "rental_type": "long_term",
                            "rooms_count": 3,
                            "area_sqm": 75.0,
                            "price": 300000,
                            "currency": "AMD",
                            "district": "Центр",
                            "address": "ул. Амиряна 13",
                            "contacts": ["+374123456789"],
                            "has_balcony": True,
                            "has_air_conditioning": True,
                            "has_internet": True,
                            "has_furniture": False,
                            "has_parking": False,
                            "has_garden": False,
                            "has_pool": False,
                            "parsing_confidence": 0.85,
                        },
                        ensure_ascii=False,
                    )
                else:
                    response = json.dumps(
                        {"is_real_estate": False, "reason": "No real estate context found"}, ensure_ascii=False
                    )

        # Simulate token usage
        prompt_tokens = len(prompt.split()) * 1.3
        completion_tokens = len(response.split()) * 1.3
        total_tokens = prompt_tokens + completion_tokens

        return {
            "response": response,
            "cost_info": {
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "total_tokens": int(total_tokens),
                "cost_usd": self._calculate_cost(int(prompt_tokens), int(completion_tokens)),
                "model_name": f"mock-{self.model}",
            },
        }

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost based on model pricing"""
        if self.model not in self.pricing:
            return 0.0

        pricing = self.pricing[self.model]
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        return float(input_cost + output_cost)

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response JSON"""
        try:
            # Clean response (remove markdown if present)
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]

            # Parse JSON
            data = json.loads(response)

            # Check if it's a real estate ad
            if not data.get("is_real_estate", False):
                logger.info("LLM determined this is not a real estate ad: %s", data.get("reason", "Unknown reason"))
                return None

            # Validate and convert data
            parsed_data = self._validate_and_convert_data(data)

            return parsed_data

        except Exception as e:
            logger.error("Error parsing LLM response: %s", e)
            return None

    def _validate_and_convert_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and convert LLM response data"""
        result: Dict[str, Any] = {}

        # Property type mapping
        property_type_mapping = {
            "apartment": "apartment",
            "room": "room",
            "house": "house",
            "studio": "room",  # Studio is treated as room type
            "commercial": "hotel_room",
        }

        if data.get("property_type"):
            mapped_type = property_type_mapping.get(data["property_type"])
            if mapped_type:
                try:
                    result["property_type"] = PropertyType(mapped_type)
                except ValueError:
                    result["property_type"] = None
            else:
                result["property_type"] = None
        else:
            result["property_type"] = None

        # Rental type mapping
        rental_type_mapping = {"long_term": "long_term", "daily": "daily"}

        if data.get("rental_type"):
            mapped_rental = rental_type_mapping.get(data["rental_type"])
            if mapped_rental:
                try:
                    result["rental_type"] = RentalType(mapped_rental)
                except ValueError:
                    result["rental_type"] = None
            else:
                result["rental_type"] = None
        else:
            result["rental_type"] = None

        # Room count
        if data.get("rooms_count") is not None:
            try:
                result["rooms_count"] = int(data["rooms_count"])
            except (ValueError, TypeError):
                result["rooms_count"] = None
        else:
            result["rooms_count"] = None

        # Area
        if data.get("area_sqm") is not None:
            try:
                result["area_sqm"] = float(data["area_sqm"])
            except (ValueError, TypeError):
                result["area_sqm"] = None
        else:
            result["area_sqm"] = None

        # Price and currency - direct mapping
        if data.get("price") is not None:
            try:
                result["price"] = float(data["price"])
                result["currency"] = data.get("currency")
            except (ValueError, TypeError):
                result["price"] = None
                result["currency"] = None
        else:
            result["price"] = None
            result["currency"] = None

        # String fields
        for field in ["district", "address", "city", "additional_notes"]:
            result[field] = data.get(field)

        # Contacts - handle both array and string
        contacts = data.get("contacts")
        if contacts:
            if isinstance(contacts, list):
                result["contacts"] = contacts
            elif isinstance(contacts, str):
                result["contacts"] = [contacts]
            else:
                result["contacts"] = []
        else:
            result["contacts"] = []

        # Boolean fields - direct mapping with null handling
        boolean_fields = [
            "has_balcony",
            "has_air_conditioning",
            "has_internet",
            "has_furniture",
            "has_parking",
            "has_garden",
            "has_pool",
            "has_elevator",
            "pets_allowed",
            "utilities_included",
        ]

        for field in boolean_fields:
            value = data.get(field)
            if value is not None:
                result[field] = bool(value)
            else:
                result[field] = None

        # Numeric fields with null handling
        numeric_fields = ["floor", "total_floors"]
        for field in numeric_fields:
            value = data.get(field)
            if value is not None:
                try:
                    result[field] = int(value)
                except (ValueError, TypeError):
                    result[field] = None
            else:
                result[field] = None

        # Confidence
        result["parsing_confidence"] = float(data.get("parsing_confidence", 0.0))

        return result

    async def _save_real_estate_ad(self, ad: RealEstateAd) -> None:
        """Save real estate ad to database"""
        try:
            db = mongodb.get_database()

            # Convert to dict for MongoDB
            ad_data = ad.model_dump(exclude={"id"})

            # Add timestamps
            ad_data["created_at"] = datetime.utcnow()
            ad_data["updated_at"] = datetime.utcnow()

            # Use replace_one with upsert to handle duplicates
            result = await db.real_estate_ads.replace_one(
                {"original_post_id": ad.original_post_id}, ad_data, upsert=True
            )

            if result.upserted_id:
                ad.id = str(result.upserted_id)
                logger.info("Inserted new real estate ad %s to database", ad.original_post_id)
            else:
                logger.info("Updated existing real estate ad %s in database", ad.original_post_id)

        except Exception as e:
            logger.error("Error saving real estate ad: %s", e)

    async def _save_llm_cost(self, post_id: int, channel_id: int, cost_info: Dict[str, Any]) -> None:
        """Save LLM cost information to database"""
        try:
            cost_record = LLMCost(
                post_id=post_id,
                channel_id=channel_id,
                prompt_tokens=cost_info["prompt_tokens"],
                completion_tokens=cost_info["completion_tokens"],
                total_tokens=cost_info["total_tokens"],
                cost_usd=cost_info["cost_usd"],
                model_name=cost_info["model_name"],
            )  # type: ignore

            db = mongodb.get_database()
            cost_data = cost_record.dict(exclude={"id"})
            await db.llm_costs.insert_one(cost_data)

            logger.info("Saved LLM cost: $%.4f for post %s", cost_info["cost_usd"], post_id)

        except Exception as e:
            logger.error("Error saving LLM cost: %s", e)
