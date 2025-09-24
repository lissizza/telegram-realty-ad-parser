"""
Unit tests for filter matching logic (without LLM)
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models.simple_filter import SimpleFilter
from app.models.telegram import PropertyType, RealEstateAd, RentalType
from app.services.simple_filter_service import SimpleFilterService


class TestFilterMatching:
    """Test class for filter matching logic"""

    @pytest.fixture
    def filter_service(self):
        """Create filter service instance for testing"""
        return SimpleFilterService()

    @pytest.fixture
    def sample_apartment_ad(self):
        """Sample apartment advertisement for testing"""
        return RealEstateAd(
            original_post_id=1,
            original_channel_id=12345,
            original_message="Test apartment",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            area_sqm=60,
            price=250000,
            currency="AMD",
            district="Центр",
            city="Ереван",
            has_balcony=True,
            has_air_conditioning=True,
            has_internet=True,
            has_furniture=True,
            pets_allowed=True,
            parsing_confidence=0.9,
        )

    @pytest.fixture
    def sample_house_ad(self):
        """Sample house advertisement for testing"""
        return RealEstateAd(
            original_post_id=2,
            original_channel_id=12345,
            original_message="Test house",
            property_type=PropertyType.HOUSE,
            rental_type=RentalType.LONG_TERM,
            rooms_count=3,
            area_sqm=120,
            price=400000,
            currency="AMD",
            district="Аван",
            city="Ереван",
            has_parking=True,
            has_garden=True,
            pets_allowed=False,
            parsing_confidence=0.8,
        )

    @pytest.fixture
    def sample_studio_ad(self):
        """Sample studio advertisement for testing"""
        return RealEstateAd(
            original_post_id=3,
            original_channel_id=12345,
            original_message="Test studio",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=1,
            area_sqm=35,
            price=180000,
            currency="AMD",
            district="Арабкир",
            city="Ереван",
            has_balcony=False,
            has_air_conditioning=False,
            has_internet=True,
            has_furniture=False,
            pets_allowed=True,
            parsing_confidence=0.7,
        )

    def test_filter_matches_property_type(self, filter_service, sample_apartment_ad):
        """Test filter matching by property type"""
        # Filter for apartments only
        filter_obj = SimpleFilter(name="Apartments Only", property_types=[PropertyType.APARTMENT], is_active=True)

        result = filter_obj.matches(sample_apartment_ad)
        assert result is True

        # Filter for houses only
        filter_obj.property_types = [PropertyType.HOUSE]
        result = filter_obj.matches(sample_apartment_ad)
        assert result is False

    def test_filter_matches_rental_type(self, filter_service, sample_apartment_ad):
        """Test filter matching by rental type"""
        # Filter for long-term only
        filter_obj = SimpleFilter(name="Long-term Only", rental_types=[RentalType.LONG_TERM], is_active=True)

        result = filter_obj.matches(sample_apartment_ad)
        assert result is True

        # Filter for daily only
        filter_obj.rental_types = [RentalType.DAILY]
        result = filter_obj.matches(sample_apartment_ad)
        assert result is False

    def test_filter_matches_rooms_count(self, filter_service, sample_apartment_ad, sample_studio_ad):
        """Test filter matching by room count"""
        # Filter for 2-3 rooms
        filter_obj = SimpleFilter(name="2-3 Rooms", min_rooms=2, max_rooms=3, is_active=True)

        result = filter_obj.matches(sample_apartment_ad)
        assert result is True  # 2 rooms matches

        result = filter_obj.matches(sample_studio_ad)
        assert result is False  # 1 room doesn't match

        # Filter for 1 room only
        filter_obj.min_rooms = 1
        filter_obj.max_rooms = 1
        result = filter_obj.matches(sample_studio_ad)
        assert result is True  # 1 room matches

    def test_filter_matches_area(self, filter_service, sample_apartment_ad, sample_studio_ad):
        """Test filter matching by area"""
        # Filter for 50-80 sqm
        filter_obj = SimpleFilter(name="50-80 sqm", min_area=50, max_area=80, is_active=True)

        result = filter_obj.matches(sample_apartment_ad)
        assert result is True  # 60 sqm matches

        result = filter_obj.matches(sample_studio_ad)
        assert result is False  # 35 sqm doesn't match

    def test_filter_matches_price(self, filter_service, sample_apartment_ad, sample_house_ad):
        """Test filter matching by price in AMD"""
        # Filter for 200k-300k AMD
        filter_obj = SimpleFilter(
            name="200k-300k AMD", min_price=200000, max_price=300000, price_currency="AMD", is_active=True
        )

        result = filter_obj.matches(sample_apartment_ad)
        assert result is True  # 250k matches

        result = filter_obj.matches(sample_house_ad)
        assert result is False  # 400k doesn't match

    def test_filter_matches_price_usd(self, filter_service):
        """Test filter matching by price in USD"""
        ad_with_usd = RealEstateAd(
            original_post_id=4,
            original_channel_id=12345,
            original_message="Test USD price",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            price=800,
            currency="USD",
            parsing_confidence=0.9,
        )

        # Filter for 500-1000 USD
        filter_obj = SimpleFilter(
            name="500-1000 USD", min_price=500, max_price=1000, price_currency="USD", is_active=True
        )

        result = filter_obj.matches(ad_with_usd)
        assert result is True  # 800 USD matches

    def test_filter_matches_district(self, filter_service, sample_apartment_ad, sample_house_ad):
        """Test filter matching by district"""
        # Filter for Центр district
        filter_obj = SimpleFilter(name="Центр Only", districts=["Центр"], is_active=True)

        result = filter_obj.matches(sample_apartment_ad)
        assert result is True  # Центр matches

        result = filter_obj.matches(sample_house_ad)
        assert result is False  # Аван doesn't match

    def test_filter_matches_boolean_features(self, filter_service, sample_apartment_ad, sample_studio_ad):
        """Test filter matching by boolean features"""
        # Filter requiring balcony and air conditioning
        filter_obj = SimpleFilter(
            name="With Balcony and AC", has_balcony=True, has_air_conditioning=True, is_active=True
        )

        result = filter_obj.matches(sample_apartment_ad)
        assert result is True  # Both features present

        result = filter_obj.matches(sample_studio_ad)
        assert result is False  # Neither feature present

    def test_filter_matches_pets_allowed(self, filter_service, sample_apartment_ad, sample_house_ad):
        """Test filter matching by pets allowed"""
        # Filter requiring pets allowed
        filter_obj = SimpleFilter(name="Pets Allowed", pets_allowed=True, is_active=True)

        result = filter_obj.matches(sample_apartment_ad)
        assert result is True  # Pets allowed

        result = filter_obj.matches(sample_house_ad)
        assert result is False  # Pets not allowed

    @pytest.mark.asyncio
    async def test_complete_filter_matching(self, filter_service, sample_apartment_ad):
        """Test complete filter matching with multiple criteria"""
        # Complex filter: 2-3 room apartment in Центр, 200k-300k AMD, with balcony
        filter_obj = SimpleFilter(
            name="2-3 Room Apartment in Center",
            property_types=[PropertyType.APARTMENT],
            rental_types=[RentalType.LONG_TERM],
            min_rooms=2,
            max_rooms=3,
            districts=["Центр"],
            min_price=200000,
            max_price=300000,
            price_currency="AMD",
            has_balcony=True,
            is_active=True,
        )

        # Mock the database and get_active_filters method
        with patch("app.services.simple_filter_service.mongodb") as mock_mongodb:
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db

            # Mock the async iterator for find()
            async def mock_find(query):
                filter_data = filter_obj.model_dump()
                filter_data["_id"] = "test_id"
                yield filter_data

            mock_db.simple_filters.find = mock_find

            result = await filter_service.check_filters(sample_apartment_ad)

        # Should match the filter
        assert len(result["matching_filters"]) == 1
        assert result["should_forward"] is True

    @pytest.mark.asyncio
    async def test_filter_no_match(self, filter_service, sample_studio_ad):
        """Test filter when no criteria match"""
        # Filter for houses only
        filter_obj = SimpleFilter(name="Houses Only", property_types=[PropertyType.HOUSE], is_active=True)

        # Mock the database and get_active_filters method
        with patch("app.services.simple_filter_service.mongodb") as mock_mongodb:
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db

            # Mock the async iterator for find()
            async def mock_find(query):
                filter_data = filter_obj.model_dump()
                filter_data["_id"] = "test_id"
                yield filter_data

            mock_db.simple_filters.find = mock_find

            result = await filter_service.check_filters(sample_studio_ad)

        # Should not match
        assert len(result["matching_filters"]) == 0
        assert result["should_forward"] is False

    @pytest.mark.asyncio
    async def test_inactive_filter_ignored(self, filter_service, sample_apartment_ad):
        """Test that inactive filters are ignored"""
        # Inactive filter that would match
        filter_obj = SimpleFilter(
            name="Inactive Filter", property_types=[PropertyType.APARTMENT], is_active=False  # Inactive
        )

        # Mock the database and get_active_filters method
        with patch("app.services.simple_filter_service.mongodb") as mock_mongodb:
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db

            # Mock the async iterator for find() - return empty for inactive filters
            async def mock_find(query):
                # Only return active filters
                if query.get("is_active") is True:
                    return
                return

            mock_db.simple_filters.find = mock_find

            result = await filter_service.check_filters(sample_apartment_ad)

        # Should not match inactive filter
        assert len(result["matching_filters"]) == 0
        assert result["should_forward"] is False

    @pytest.mark.asyncio
    async def test_multiple_filters_matching(self, filter_service, sample_apartment_ad):
        """Test when multiple filters match"""
        # Create multiple filters that would match
        filters = [
            SimpleFilter(name="Apartments", property_types=[PropertyType.APARTMENT], is_active=True),
            SimpleFilter(name="Long-term", rental_types=[RentalType.LONG_TERM], is_active=True),
            SimpleFilter(name="With Balcony", has_balcony=True, is_active=True),
        ]

        # Mock the database and get_active_filters method
        with patch("app.services.simple_filter_service.mongodb") as mock_mongodb:
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db

            # Mock the async iterator for find()
            async def mock_find(query):
                for i, filter_obj in enumerate(filters):
                    filter_data = filter_obj.model_dump()
                    filter_data["_id"] = f"test_id_{i}"
                    yield filter_data

            mock_db.simple_filters.find = mock_find

            result = await filter_service.check_filters(sample_apartment_ad)

        # Should match all three filters
        assert len(result["matching_filters"]) == 3
        assert result["should_forward"] is True

    def test_real_3_room_apartment_filter(self):
        """Test with real 3-room apartment advertisement"""
        # Создаем реальное объявление с 3 комнатами (как в базе)
        real_estate_ad = RealEstateAd(
            original_post_id=119488,
            original_channel_id=-1001827102719,
            original_message="◾️3 комнатная \n2 спальни✔️\n65 кв \nкаменое здание \n\n◽️Центр📍\nМаштоца пр-т 14\n\n\n◾️300,000 драм📌",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=3,
            area_sqm=65.0,
            price=300000.0,
            currency="AMD",
            district="Центр",
            address="Маштоца пр-т 14",
            city="Ереван",
            is_real_estate=True,
            parsing_confidence=0.95,
        )

        # Создаем фильтр "3-4 Room Apartment Filter"
        filter_obj = SimpleFilter(
            name="3-4 Room Apartment Filter",
            property_types=[PropertyType.APARTMENT],
            min_rooms=3,
            max_rooms=4,
            is_active=True,
        )

        print(f"\n=== ТЕСТ РЕАЛЬНОГО ОБЪЯВЛЕНИЯ ===")
        print(f"Объявление:")
        print(f"  Property type: {real_estate_ad.property_type}")
        print(f"  Rooms: {real_estate_ad.rooms_count}")
        print(f"  Price: {real_estate_ad.price} {real_estate_ad.currency}")
        print(f"  District: {real_estate_ad.district}")
        print()

        print(f"Фильтр:")
        print(f"  Name: {filter_obj.name}")
        print(f"  Property types: {filter_obj.property_types}")
        print(f"  Min rooms: {filter_obj.min_rooms}")
        print(f"  Max rooms: {filter_obj.max_rooms}")
        print()

        # Тестируем сравнение property_type
        print("=== ОТЛАДКА СРАВНЕНИЯ ===")
        print(f"ad.property_type = {real_estate_ad.property_type}")
        print(f"filter.property_types = {filter_obj.property_types}")
        print(
            f"ad.property_type in filter.property_types = {real_estate_ad.property_type in filter_obj.property_types}"
        )
        print(f"ad.property_type == PropertyType.APARTMENT = {real_estate_ad.property_type == PropertyType.APARTMENT}")
        print(
            f"PropertyType.APARTMENT in filter.property_types = {PropertyType.APARTMENT in filter_obj.property_types}"
        )
        print()

        # Тестируем сравнение rooms
        print("=== ОТЛАДКА КОМНАТ ===")
        print(f"ad.rooms_count = {real_estate_ad.rooms_count}")
        print(f"filter.min_rooms = {filter_obj.min_rooms}")
        print(f"filter.max_rooms = {filter_obj.max_rooms}")
        print(f"ad.rooms_count >= filter.min_rooms = {real_estate_ad.rooms_count >= filter_obj.min_rooms}")
        print(f"ad.rooms_count <= filter.max_rooms = {real_estate_ad.rooms_count <= filter_obj.max_rooms}")
        print()

        # Тестируем полный метод matches
        print("=== РЕЗУЛЬТАТ ФИЛЬТРАЦИИ ===")
        result = filter_obj.matches(real_estate_ad)
        print(f"filter.matches(ad) = {result}")

        if result:
            print("✅ ОБЪЯВЛЕНИЕ ДОЛЖНО ПРОЙТИ ФИЛЬТР!")
        else:
            print("❌ ОБЪЯВЛЕНИЕ НЕ ПРОХОДИТ ФИЛЬТР!")

        # Проверяем, что фильтр должен сработать
        assert result is True, f"3-room apartment should match 3-4 room filter"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
