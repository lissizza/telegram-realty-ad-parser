"""
LLM Service for real estate ad parsing.

This module provides functionality to parse real estate advertisements using
various LLM providers (OpenAI, Anthropic, local models) and extract structured
information from unstructured text.
"""

import json
import logging
import re
import time
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
from app.services.llm_quota_service import llm_quota_service
from app.services.llm_config_service import llm_config_service
from app.services.encryption_service import encryption_service

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM-based real estate ad parsing with multiple providers"""

    def __init__(self) -> None:
        # Try to load active config from database first, fallback to settings
        self._load_config()
        
        # Warn if using deprecated GLM-4-Plus model
        if self.provider == "zai" and self.model.lower() in ["glm-4-plus", "glm-4.plus", "glm-4-plus"]:
            logger.warning("Model %s is deprecated or not supported. Please use glm-4.6, glm-4.5, or glm-4.5-air instead", self.model)
        
        # Initialize client based on provider
        self._initialize_client()

        # LLM pricing (per 1K tokens)
        # Z.AI pricing: approximate values (adjust based on actual pricing)
        self.pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
            # Z.AI GLM models (approximate pricing - adjust based on actual Z.AI pricing)
            # Supported models for GLM Coding Plan: glm-4.6, glm-4.5, glm-4.5-air
            # Note: GLM-4-Plus is not supported - use glm-4.6 instead
            "glm-4.6": {"input": 0.001, "output": 0.002},
            "glm-4-6": {"input": 0.001, "output": 0.002},
            "glm-4.5": {"input": 0.001, "output": 0.002},
            "glm-4-5": {"input": 0.001, "output": 0.002},
            "glm-4.5-air": {"input": 0.001, "output": 0.002},
            "glm-4-5-air": {"input": 0.001, "output": 0.002},
            "glm-4-plus": {"input": 0.001, "output": 0.002},  # Deprecated - use glm-4.6
            "GLM-4-Plus": {"input": 0.001, "output": 0.002},  # Deprecated - use glm-4.6
            "glm-4-32b-0414-128k": {"input": 0.001, "output": 0.002},
        }
    
    def _load_config(self) -> None:
        """Load LLM configuration from database or fallback to settings"""
        try:
            # Try to get active config from database (synchronous check)
            # Note: This is a best-effort check. For async operations, use reload_config()
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, we can't use it synchronously
                    # Fallback to settings
                    self._load_from_settings()
                    return
            except RuntimeError:
                # No event loop, create a new one
                pass
            
            # Try to get active config (only if we can run async code)
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                config = loop.run_until_complete(llm_config_service.get_active_config(include_key=True))
                loop.close()
                
                if config:
                    self.provider = str(config["provider"]).lower()
                    self.model = str(config["model"])
                    self.api_key = str(config["api_key"])
                    self.base_url = config.get("base_url")
                    self.max_tokens = config.get("max_tokens", 1000)
                    self.temperature = config.get("temperature", 0.1)
                    logger.info("Loaded LLM config from database: %s (%s)", config["name"], config["model"])
                    return
            except Exception as e:
                logger.debug("Could not load config from database (will use settings): %s", e)
            
            # Fallback to settings
            self._load_from_settings()
        except Exception as e:
            logger.warning("Error loading LLM config, using settings: %s", e)
            self._load_from_settings()
    
    def _load_from_settings(self) -> None:
        """Load configuration from settings"""
        self.provider = str(settings.LLM_PROVIDER).lower()
        self.model = str(settings.LLM_MODEL)
        self.api_key = str(settings.LLM_API_KEY)
        self.base_url = settings.LLM_BASE_URL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        logger.info("Loaded LLM config from settings: provider=%s, model=%s", self.provider, self.model)
    
    async def reload_config(self) -> None:
        """Reload LLM configuration from database (async)"""
        try:
            config = await llm_config_service.get_active_config(include_key=True)
            if config:
                self.provider = str(config["provider"]).lower()
                self.model = str(config["model"])
                self.api_key = str(config["api_key"])
                self.base_url = config.get("base_url")
                self.max_tokens = config.get("max_tokens", 1000)
                self.temperature = config.get("temperature", 0.1)
                self._initialize_client()
                logger.info("Reloaded LLM config from database: %s (%s)", config["name"], config["model"])
            else:
                logger.warning("No active config in database, keeping current settings")
        except Exception as e:
            logger.error("Error reloading LLM config: %s", e)
    
    def _initialize_client(self) -> None:
        """Initialize LLM client based on current provider settings"""
        self.client: Optional[Any] = None
        if self.provider == "openai":
            self.client = AsyncOpenAI(api_key=self.api_key)
        elif self.provider == "zai":
            # Z.AI supports OpenAI-compatible protocol
            # Use base_url from config or default Z.AI endpoint
            zai_base_url = self.base_url or "https://api.z.ai/api/paas/v4"
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=zai_base_url)
            logger.info("Initialized Z.AI client with base_url: %s, model: %s", zai_base_url, self.model)
        elif self.provider == "anthropic":
            self.client = AsyncAnthropic(api_key=self.api_key)
        elif self.provider == "local":
            # For local models (Ollama, etc.)
            self.client = None  # Will use httpx directly
        elif self.provider == "mock":
            self.client = None  # Mock implementation

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
            llm_start_time = time.time()
            llm_result = await self._call_llm(prompt)
            llm_response_time = time.time() - llm_start_time
            
            logger.info("LLM API call completed for message %s in %.2f seconds", post_id, llm_response_time)
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
            # LLM quota/rate limit exceeded (OpenAI, Z.AI, or Anthropic)
            if isinstance(e, OpenAIRateLimitError):
                provider = "zai" if self.provider == "zai" else "openai"
            else:
                provider = "anthropic"
            error_str = str(e).lower()
            
            # Check error type: quota (insufficient balance) vs concurrency/rate limit
            is_quota_error = False
            is_concurrency_error = False
            
            # Check error structure for OpenAI/Z.AI
            if isinstance(e, OpenAIRateLimitError):
                # Try to extract JSON from error message
                json_match = re.search(r'\{.*\}', str(e))
                if json_match:
                    try:
                        error_data = json.loads(json_match.group())
                        error_info = error_data.get('error', {})
                        error_type = error_info.get('type', '').lower()
                        error_code = str(error_info.get('code', '')).lower()
                        error_message = error_info.get('message', '').lower()
                        
                        # Check for concurrency limit (Z.AI specific error code 1302)
                        if error_code == '1302' or 'high concurrency' in error_message or 'concurrency' in error_message:
                            is_concurrency_error = True
                        # Check for quota error
                        elif error_type == 'insufficient_quota' or error_code == 'insufficient_quota':
                            is_quota_error = True
                    except (json.JSONDecodeError, AttributeError):
                        pass
                
                # Fallback string checks
                if not is_quota_error and not is_concurrency_error:
                    if '1302' in str(e) or 'high concurrency' in error_str or 'concurrency' in error_str:
                        is_concurrency_error = True
                    elif "insufficient_quota" in error_str or ("'type': 'insufficient_quota'" in str(e)) or ("'code': 'insufficient_quota'" in str(e)):
                        is_quota_error = True
            else:
                # Anthropic - check string
                is_quota_error = (
                    "insufficient_quota" in error_str or
                    ("quota" in error_str and "rate" not in error_str) or
                    "billing" in error_str or
                    "payment" in error_str
                )
            
            if is_quota_error:
                # Quota exceeded (no balance) - stop processing
                logger.error("LLM quota exceeded (insufficient balance) while parsing message %s (provider: %s): %s", post_id, provider, e)
                llm_quota_service.set_quota_exceeded()
                
                # Notify super admins
                try:
                    asyncio.create_task(admin_notification_service.notify_quota_exceeded(str(e)))
                except Exception as notify_error:
                    logger.error("Error creating notification task: %s", notify_error)
                
                # Raise custom exception with quota flag
                raise LLMQuotaExceededError(str(e), provider=provider, original_error=e, is_quota=True)
            elif is_concurrency_error:
                # Concurrency limit exceeded - temporary, will retry
                logger.warning("LLM concurrency limit exceeded while parsing message %s (provider: %s): %s. Will retry with backoff.", post_id, provider, e)
                # Raise custom exception with concurrency flag
                raise LLMQuotaExceededError(str(e), provider=provider, original_error=e, is_concurrency=True)
            else:
                # Generic rate limit error - temporary, will retry
                logger.warning("LLM rate limit hit while parsing message %s (provider: %s): %s. Will retry later.", post_id, provider, e)
                # Raise generic rate limit exception
                raise LLMQuotaExceededError(str(e), provider=provider, original_error=e, is_rate_limit=True)
        except (OpenAIAPIError, Exception) as e:
            # Other errors (API errors, parsing errors, etc.)
            logger.error("Error parsing with LLM: %s", e)
            return None

    def _create_parsing_prompt(self, text: str) -> str:
        """Create prompt for LLM parsing"""
        return f"""Parse real estate ad from Russian/Armenian Telegram post.

IMPORTANT: Return ONLY valid JSON, no explanations or markdown.

CLASSIFICATION:
- OFFER (сдаю, сдается, продаю, продается) → is_real_estate: true
- SEARCH (ищу, сниму, нужна) → is_real_estate: false

KEY RULES:
- "X/Y этаж" = floor X of Y total (NOT rooms)
- Studio (студия, однушка) = 1 room
- Use null for missing data

REQUIRED JSON FORMAT:
{{
  "is_real_estate": true,
  "parsing_confidence": 0.9,
  "property_type": "apartment",
  "rental_type": "long_term",
  "rooms_count": 2,
  "area_sqm": 55.0,
  "price": 45000,
  "currency": "AMD",
  "city": "Ереван",
  "district": "Кентрон",
  "address": "улица Маштоца 25",
  "contacts": ["@username"],
  "has_balcony": true,
  "has_air_conditioning": null,
  "has_internet": true,
  "has_furniture": true,
  "has_parking": null,
  "has_garden": null,
  "has_pool": null,
  "has_elevator": true,
  "pets_allowed": false,
  "utilities_included": null,
  "floor": 5,
  "total_floors": 9,
  "additional_notes": null
}}

TEXT TO PARSE:
{text}

Return ONLY the JSON object, no other text:"""

    async def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call LLM API based on provider - may raise RateLimitError"""
        if self.provider == "openai":
            return await self._call_openai(prompt)
        if self.provider == "zai":
            # Z.AI uses OpenAI-compatible protocol, so we can use the same method
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
        """Call OpenAI-compatible API (OpenAI or Z.AI) - raises exceptions on errors"""
        if not self.client or not hasattr(self.client, "chat"):
            provider_name = "Z.AI" if self.provider == "zai" else "OpenAI"
            logger.error("%s client not properly initialized", provider_name)
            return None

        provider_name = "Z.AI" if self.provider == "zai" else "OpenAI"
        
        # Log prompt size for diagnostics
        prompt_chars = len(prompt)
        prompt_words = len(prompt.split())
        logger.debug("Calling %s API: model=%s, prompt_size=%d chars (%d words), max_tokens=%d", 
                    provider_name, self.model, prompt_chars, prompt_words, self.max_tokens)
        
        api_start_time = time.time()
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
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
                ),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            logger.error("%s API call timed out after 60 seconds for model: %s", provider_name, self.model)
            return None

        api_response_time = time.time() - api_start_time
        
        content = response.choices[0].message.content
        usage = response.usage

        if not usage:
            logger.error("No usage information in %s response", provider_name)
            return None
        
        # Log detailed timing and token usage
        logger.info(
            "%s API call: %.2fs | tokens: %d prompt + %d completion = %d total | model: %s",
            provider_name,
            api_response_time,
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.total_tokens,
            self.model
        )
        
        # Check if response has rate limit info (some providers include it)
        if hasattr(response, '_headers'):
            headers = response._headers
            if 'x-ratelimit-remaining' in headers:
                logger.info("Rate limit remaining: %s", headers.get('x-ratelimit-remaining'))
            if 'x-ratelimit-limit' in headers:
                logger.info("Rate limit total: %s", headers.get('x-ratelimit-limit'))

        return {
            "response": content,
            "cost_info": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cost_usd": self._calculate_cost(usage.prompt_tokens, usage.completion_tokens),
                "model_name": self.model,
            },
            "response_time_seconds": api_response_time,
        }

    async def _call_anthropic(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call Anthropic API - raises exceptions on errors"""
        if not self.client or not hasattr(self.client, "messages"):
            logger.error("Anthropic client not properly initialized")
            return None

        api_start_time = time.time()
        try:
            response = await asyncio.wait_for(
                self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            logger.error("Anthropic API call timed out after 60 seconds for model: %s", self.model)
            return None
        api_response_time = time.time() - api_start_time
        logger.debug("Anthropic API responded in %.2f seconds", api_response_time)

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
            "response_time_seconds": api_response_time,
        }

    async def _call_local(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call local LLM API (Ollama, etc.)"""
        try:
            if not self.base_url:
                logger.error("LLM_BASE_URL not configured for local provider")
                return None

            async with httpx.AsyncClient() as client:
                api_start_time = time.time()
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
                api_response_time = time.time() - api_start_time
                logger.debug("Local LLM API responded in %.2f seconds", api_response_time)
                
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
                    "response_time_seconds": api_response_time,
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
            # Log raw response for debugging
            logger.debug("Raw LLM response (first 500 chars): %s", response[:500] if response else "EMPTY")
            
            # Clean response (remove markdown if present)
            response = response.strip()
            if not response:
                logger.error("Empty LLM response received")
                return None
                
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            # Parse JSON
            data = json.loads(response)

            # Check if it's a real estate ad
            if not data.get("is_real_estate", False):
                logger.info("LLM determined this is not a real estate ad: %s", data.get("reason", "Unknown reason"))
                return None

            # Validate and convert data
            parsed_data = self._validate_and_convert_data(data)

            return parsed_data

        except json.JSONDecodeError as e:
            logger.error("JSON decode error: %s. Response (first 200 chars): %s", e, response[:200] if response else "EMPTY")
            return None
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

        # Price and currency - direct mapping with validation
        if data.get("price") is not None:
            try:
                result["price"] = float(data["price"])
                # Validate currency if provided, default to AMD if not specified or invalid
                currency_value = data.get("currency")
                from app.models.telegram import Currency
                if currency_value is not None:
                    try:
                        # Try to convert to Currency enum
                        result["currency"] = Currency(currency_value)
                    except (ValueError, TypeError):
                        # Invalid currency value, use default AMD
                        result["currency"] = Currency.AMD
                else:
                    # Currency not specified, use default AMD
                    result["currency"] = Currency.AMD
            except (ValueError, TypeError):
                result["price"] = None
                result["currency"] = Currency.AMD  # Default to AMD even if price parsing failed
        else:
            result["price"] = None
            result["currency"] = Currency.AMD  # Default to AMD if no price

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
