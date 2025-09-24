"""
Test for floor vs room count parsing issue
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.llm_service import LLMService


class TestFloorParsing:
    """Test that LLM correctly distinguishes between floor info and room count"""

    @pytest.fixture
    def llm_service(self):
        """Create LLMService instance for testing"""
        return LLMService()

    @pytest.mark.asyncio
    async def test_floor_info_not_room_count(self, llm_service):
        """Test that '3/8 этаж' is parsed as floor info, not 3 rooms"""
        # Test text with floor info but no room count
        test_text = "Рубен Севака 26\n3/8 этаж\n500.000драм\nБез комиссии"

        # Mock the LLM response
        mock_response = {
            "response": '''{
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
}''',
            "cost_info": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "cost_usd": 0.001,
                "model_name": "gpt-3.5-turbo"
            }
        }

        with patch.object(llm_service, '_call_llm', return_value=mock_response):
            with patch.object(llm_service, '_save_real_estate_ad', return_value=None):

                # Execute
                result = await llm_service.parse_with_llm(
                    text=test_text,
                    post_id=12345,
                    channel_id=-1001234567890,
                    incoming_message_id="test_id",
                    topic_id=2629
                )

                # Verify
                assert result is not None
                assert result.rooms_count is None  # Should be null, not 3
                assert result.floor == 3
                assert result.total_floors == 8
                assert result.price == 500000
                assert result.currency == "AMD"
                assert "floor information" in result.additional_notes.lower()

    @pytest.mark.asyncio
    async def test_room_count_with_floor_info(self, llm_service):
        """Test that '2к квартира, 5/9 этаж' correctly parses both room count and floor"""
        # Test text with both room count and floor info
        test_text = "Сдаю 2к квартиру, 5/9 этаж, 55кв.м, 45000₽/мес"

        # Mock the LLM response
        mock_response = {
            "response": '''{
  "is_real_estate": true,
  "parsing_confidence": 0.95,
  "property_type": "apartment",
  "rental_type": "long_term",
  "rooms_count": 2,
  "area_sqm": 55,
  "price": 45000,
  "currency": "RUB",
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
  "floor": 5,
  "total_floors": 9,
  "city": null,
  "additional_notes": null
}''',
            "cost_info": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "cost_usd": 0.001,
                "model_name": "gpt-3.5-turbo"
            }
        }
        
        with patch.object(llm_service, '_call_llm', return_value=mock_response):
            with patch.object(llm_service, '_save_real_estate_ad', return_value=None):
                
                # Execute
                result = await llm_service.parse_with_llm(
                    text=test_text,
                    post_id=12346,
                    channel_id=-1001234567890,
                    incoming_message_id="test_id2",
                    topic_id=2629
                )
                
                # Verify
                assert result is not None
                assert result.rooms_count == 2  # Should be 2 rooms
                assert result.floor == 5
                assert result.total_floors == 9
                assert result.area_sqm == 55
                assert result.price == 45000
                assert result.currency == "RUB"
    
    @pytest.mark.asyncio
    async def test_various_floor_formats(self, llm_service):
        """Test various floor format expressions"""
        test_cases = [
            ("3/8 этаж", 3, 8),
            ("на 5 этаже", 5, None),
            ("7-й этаж", 7, None),
            ("2 этаж из 10", 2, 10),
        ]
        
        for floor_text, expected_floor, expected_total in test_cases:
            test_text = f"Сдаю квартиру, {floor_text}, 100000 драм"
            
            # Mock the LLM response
            mock_response = {
                "response": f'''{{
  "is_real_estate": true,
  "parsing_confidence": 0.8,
  "property_type": "apartment",
  "rental_type": "long_term",
  "rooms_count": null,
  "area_sqm": null,
  "price": 100000,
  "currency": "AMD",
  "floor": {expected_floor},
  "total_floors": {expected_total if expected_total else "null"},
  "additional_notes": "Floor info: {floor_text}"
}}''',
                "cost_info": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                    "cost_usd": 0.001,
                    "model_name": "gpt-3.5-turbo"
                }
            }
            
            with patch.object(llm_service, '_call_llm', return_value=mock_response):
                with patch.object(llm_service, '_save_real_estate_ad', return_value=None):
                    
                    # Execute
                    result = await llm_service.parse_with_llm(
                        text=test_text,
                        post_id=12347,
                        channel_id=-1001234567890,
                        incoming_message_id="test_id3",
                        topic_id=2629
                    )
                    
                    # Verify
                    assert result is not None
                    assert result.rooms_count is None  # Should never be set from floor info
                    assert result.floor == expected_floor
                    if expected_total:
                        assert result.total_floors == expected_total
                    else:
                        assert result.total_floors is None
