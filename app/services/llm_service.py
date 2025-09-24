import logging
import json
from typing import Optional, Dict, Any

import httpx
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from app.core.config import settings
from app.models.telegram import RealEstateAd, PropertyType, RentalType
from app.models.llm_cost import LLMCost

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM-based real estate ad parsing with multiple providers"""
    
    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self.model = settings.LLM_MODEL
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_BASE_URL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        
        # Initialize client based on provider
        self.client = None
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
        
    async def parse_with_llm(self, text: str, post_id: int, channel_id: int, incoming_message_id: str = None, topic_id: int = None) -> Optional[RealEstateAd]:
        """Parse real estate ad using LLM"""
        try:
            # Create parsing prompt
            prompt = self._create_parsing_prompt(text)
            
            # Call LLM
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
                **parsed_data
            )
            
            # Save to database (all LLM results are saved)
            await self._save_real_estate_ad(ad)
            
            return ad
            
        except Exception as e:
            logger.error(f"Error parsing with LLM: {e}")
            return None
    
    def _create_parsing_prompt(self, text: str) -> str:
        """Create prompt for LLM parsing"""
        return f"""You are a real estate listing parser for Russian Telegram posts. Extract structured information into JSON format.

INSTRUCTIONS:
1. Analyze if message is genuine real estate listing
2. Extract all available parameters using context clues
3. Handle language variations and informal writing
4. Use null for missing data, don't guess
5. Return confidence score based on extraction certainty

RUSSIAN TERMS:
Rent: сдаю, сдам, сдается, аренда, снять, в аренду
Sale: продаю, продам, продается, купить, продажа  
Want rent: сниму, ищу, нужна, требуется
Apartment: квартира, кв, квартиру
Room: комната, ком, комнату
House: дом, коттедж, таунхаус
Studio: студия, однушка
Commercial: офис, магазин, склад
Room counts: 1к, 1-к, однокомнатная, однушка, 2к, 2-к, двухкомнатная, двушка, 3к, трешка, 4к
Floor info: X/Y этаж, X/Y этаж, на X этаже, X-й этаж (X = current floor, Y = total floors)
Long-term: долгосрочно, долгосрок, на длительный срок
Short-term: посуточно, на сутки, краткосрок, суточно

IMPORTANT: 
- "3/8 этаж" means floor 3 of 8 total floors, NOT 3 rooms
- "X/Y этаж" format is ALWAYS about floors, never rooms
- Only count rooms when explicitly mentioned: "2к", "двушка", "3 комнаты", etc.
- If only floor info is given without room count, set rooms_count to null

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

EXTRACTION RULES:
- If information is not available, use null
- For boolean fields, use true/false
- For arrays, use empty array [] if no data
- Extract phone numbers with country code if available, otherwise add appropriate country code based on city/address context
- Extract Telegram usernames as @username
- For districts, use standard Yerevan district names
- For city, extract main city name (Ереван, Москва, Санкт-Петербург, etc.)
- For address, extract street names, building numbers, metro stations

NOTES:
- Mark is_real_estate false for spam, jobs, services
- Extract prices with currency symbols or words like рублей, тысяч, драм, долларов, евро, фунтов
- Recognize metro stations and street names in addresses
- Lower confidence for ambiguous listings
- Handle creative abbreviations and informal language
- For ambiguous or unclear information, document your reasoning in additional_notes
- If multiple prices are mentioned (e.g., monthly vs yearly), choose the most relevant one and note the ambiguity in additional_notes
- If room count is unclear or could be interpreted differently, explain in additional_notes
- For any parsing decisions that might be controversial, add explanation to additional_notes

Analyze this real estate text and return JSON:

{text}"""
    
    async def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call LLM API based on provider"""
        try:
            if self.provider == "openai":
                return await self._call_openai(prompt)
            elif self.provider == "anthropic":
                return await self._call_anthropic(prompt)
            elif self.provider == "local":
                return await self._call_local(prompt)
            elif self.provider == "mock":
                return await self._call_mock(prompt)
            else:
                logger.error(f"Unknown LLM provider: {self.provider}")
                return None
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return None
    
    async def _call_openai(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call OpenAI API"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing real estate advertisements in Armenian and Russian languages."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            content = response.choices[0].message.content
            usage = response.usage
            
            return {
                "response": content,
                "cost_info": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost_usd": self._calculate_cost(usage.prompt_tokens, usage.completion_tokens),
                    "model_name": self.model
                }
            }
        except Exception as e:
            logger.error(f"Error calling OpenAI: {e}")
            return None
    
    async def _call_anthropic(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call Anthropic API"""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.content[0].text
            usage = response.usage
            
            return {
                "response": content,
                "cost_info": {
                    "prompt_tokens": usage.input_tokens,
                    "completion_tokens": usage.output_tokens,
                    "total_tokens": usage.input_tokens + usage.output_tokens,
                    "cost_usd": self._calculate_cost(usage.input_tokens, usage.output_tokens),
                    "model_name": self.model
                }
            }
        except Exception as e:
            logger.error(f"Error calling Anthropic: {e}")
            return None
    
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
                            {"role": "system", "content": "You are an expert at analyzing real estate advertisements in Armenian and Russian languages."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": self.max_tokens,
                        "temperature": self.temperature
                    },
                    timeout=60.0
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
                        "model_name": self.model
                    }
                }
        except Exception as e:
            logger.error(f"Error calling local LLM: {e}")
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
        spam_indicators = ["билет", "ticket", "концерт", "standup", "спам", "реклама", "крипто", "заработок", "мероприятие", "event", "gastro", "tour"]
        if any(indicator in text_lower for indicator in spam_indicators):
            response = json.dumps({
                "is_real_estate": False,
                "reason": "Contains spam indicators or non-real-estate content"
            }, ensure_ascii=False)
        else:
            # Check for real estate context
            real_estate_indicators = [
                "сдаю", "сдаётся", "сдается", "сдам", "сдаём", "аренд", "аренда", "аренду",
                "предлагаю", "предлагаем", "предлагает", "предложение",
                "квартир", "дом", "комнат", "жилье", "недвижимость", "апартамент",
                "кв.м", "кв м", "квадрат", "площадь", "этаж", "этажей", "подъезд",
                "балкон", "лоджия", "кухня", "ванная", "туалет", "коридор",
                "мебель", "меблирован", "ремонт", "новостройка", "современный",
                "цена", "стоимость", "драм", "доллар", "usd", "$", "₽", "руб",
                "свяжитесь", "пишите", "звоните", "телефон", "контакт",
                "ереван", "центр", "кентрон", "арабкир", "малатия", "эребуни",
                "шахумян", "канакер", "аван", "нор-норк", "шенгавит"
            ]
            
            indicator_count = sum(1 for indicator in real_estate_indicators if indicator in text_lower)
            
            # Check for price patterns
            import re
            price_patterns = [
                r'\d+\s*000?\s*драм',
                r'\d+\s*000?\s*₽',
                r'\$\d+',
                r'\d+\s*доллар',
                r'\d+\s*usd',
                r'\d+\s*к\s*драм',
            ]
            has_price = any(re.search(pattern, text_lower) for pattern in price_patterns)
            
            # Check for numeric values
            has_numbers = bool(re.search(r'\d+', text))
            
            # Determine if it's real estate
            is_real_estate = (
                indicator_count >= 1 or
                (has_price and has_numbers) or
                (has_numbers and "квартир" in text_lower) or
                (has_numbers and "комнат" in text_lower) or
                (has_numbers and "дом" in text_lower) or
                ("сдаётся" in text_lower) or
                ("сдается" in text_lower) or
                ("сдаю" in text_lower) or
                ("сдам" in text_lower) or
                ("сдаём" in text_lower)
            )
            
            if is_real_estate:
                # Simulate real estate ad parsing
                response = json.dumps({
                    "is_real_estate": True,
                    "property_type": "apartment",
                    "rental_type": "long_term",
                    "rooms_count": 3,
                    "area_sqm": 75.0,
                    "price_amd": 300000,
                    "price_usd": None,
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
                    "parsing_confidence": 0.85
                }, ensure_ascii=False)
            else:
                response = json.dumps({
                    "is_real_estate": False,
                    "reason": "No real estate context found"
                }, ensure_ascii=False)
        
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
                "cost_usd": self._calculate_cost(prompt_tokens, completion_tokens),
                "model_name": f"mock-{self.model}"
            }
        }
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost based on model pricing"""
        if self.model not in self.pricing:
            return 0.0
        
        pricing = self.pricing[self.model]
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        return input_cost + output_cost
    
    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response JSON"""
        try:
            # Clean response (remove markdown if present)
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            
            # Parse JSON
            data = json.loads(response)
            
            # Check if it's a real estate ad
            if not data.get("is_real_estate", False):
                logger.info(f"LLM determined this is not a real estate ad: {data.get('reason', 'Unknown reason')}")
                return None
            
            # Validate and convert data
            parsed_data = self._validate_and_convert_data(data)
            
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return None
    
    def _validate_and_convert_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and convert LLM response data"""
        result = {}
        
        # Property type mapping
        property_type_mapping = {
            "apartment": "apartment",
            "room": "room", 
            "house": "house",
            "studio": "room",  # Studio is treated as room type
            "commercial": "hotel_room"
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
        
        # Rental type mapping
        rental_type_mapping = {
            "long_term": "long_term",
            "daily": "daily"
        }
        
        if data.get("rental_type"):
            mapped_rental = rental_type_mapping.get(data["rental_type"])
            if mapped_rental:
                try:
                    result["rental_type"] = RentalType(mapped_rental)
                except ValueError:
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
            "has_balcony", "has_air_conditioning", "has_internet", "has_furniture",
            "has_parking", "has_garden", "has_pool", "has_elevator", 
            "pets_allowed", "utilities_included"
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
            from app.db.mongodb import mongodb
            db = mongodb.get_database()
            
            # Convert to dict for MongoDB
            ad_data = ad.model_dump(exclude={"id"})
            
            # Add timestamps
            from datetime import datetime
            ad_data["created_at"] = datetime.utcnow()
            ad_data["updated_at"] = datetime.utcnow()
            
            # Use replace_one with upsert to handle duplicates
            result = await db.real_estate_ads.replace_one(
                {"original_post_id": ad.original_post_id}, 
                ad_data, 
                upsert=True
            )
            
            if result.upserted_id:
                ad.id = str(result.upserted_id)
                logger.info(f"Inserted new real estate ad {ad.original_post_id} to database")
            else:
                logger.info(f"Updated existing real estate ad {ad.original_post_id} in database")
            
        except Exception as e:
            logger.error(f"Error saving real estate ad: {e}")

    async def _save_llm_cost(self, post_id: int, channel_id: int, cost_info: Dict[str, Any]):
        """Save LLM cost information to database"""
        try:
            from app.db.mongodb import mongodb
            
            cost_record = LLMCost(
                post_id=post_id,
                channel_id=channel_id,
                prompt_tokens=cost_info["prompt_tokens"],
                completion_tokens=cost_info["completion_tokens"],
                total_tokens=cost_info["total_tokens"],
                cost_usd=cost_info["cost_usd"],
                model_name=cost_info["model_name"]
            )
            
            db = mongodb.get_database()
            cost_data = cost_record.dict(exclude={"id"})
            await db.llm_costs.insert_one(cost_data)
            
            logger.info(f"Saved LLM cost: ${cost_info['cost_usd']:.4f} for post {post_id}")
            
        except Exception as e:
            logger.error(f"Error saving LLM cost: {e}")