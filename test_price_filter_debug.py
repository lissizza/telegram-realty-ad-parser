#!/usr/bin/env python3
"""
Тест для отладки проблемы с ценовыми фильтрами
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.models.price_filter import PriceFilter
from app.models.simple_filter import SimpleFilter

def test_price_filtering():
    """Тестируем фильтрацию цен"""
    
    # Создаем ценовые фильтры как в базе данных
    price_filters = [
        PriceFilter(
            id="68d68aa84f48f2b4946d4332",
            filter_id="68d67386f3e2b406ba675b17",
            min_price=None,
            max_price=350000.0,
            currency="AMD",
            is_active=True
        ),
        PriceFilter(
            id="68d68aa84f48f2b4946d4333",
            filter_id="68d67386f3e2b406ba675b17",
            min_price=None,
            max_price=800.0,
            currency="USD",
            is_active=True
        )
    ]
    
    # Создаем простой фильтр
    simple_filter = SimpleFilter(
        id="68d67386f3e2b406ba675b17",
        user_id=223720761,
        name="Test Filter",
        min_rooms=3,
        max_rooms=6,
        property_types=["apartment"],
        is_active=True
    )
    
    # Тестируем объявление за 1,400 USD
    class MockAd:
        def __init__(self, price, currency, rooms_count, property_type):
            self.price = price
            self.currency = currency
            self.rooms_count = rooms_count
            self.property_type = property_type
            self.district = None
            self.original_channel_id = None
            self.has_balcony = None
            self.has_air_conditioning = None
            self.has_internet = None
            self.has_furniture = None
            self.has_parking = None
            self.has_garden = None
            self.has_pool = None
            self.has_elevator = None
            self.pets_allowed = None
            self.utilities_included = None
    
    # Тест 1: Объявление за 1,400 USD (должно быть отсеяно)
    ad_1400_usd = MockAd(price=1400.0, currency="USD", rooms_count=4, property_type="apartment")
    
    print("=== Тест 1: Объявление за 1,400 USD ===")
    print(f"Цена: {ad_1400_usd.price} {ad_1400_usd.currency}")
    print(f"Комнаты: {ad_1400_usd.rooms_count}")
    print(f"Тип: {ad_1400_usd.property_type}")
    
    # Проверяем каждый ценовой фильтр отдельно
    for i, pf in enumerate(price_filters):
        matches = pf.matches_price(ad_1400_usd.price, ad_1400_usd.currency)
        print(f"Ценовой фильтр {i+1}: {pf.currency} max={pf.max_price} -> {matches}")
    
    # Проверяем общую фильтрацию
    matches = simple_filter.matches_with_price_filters(ad_1400_usd, price_filters)
    print(f"Общий результат: {matches}")
    print()
    
    # Тест 2: Объявление за 700 USD (должно пройти)
    ad_700_usd = MockAd(price=700.0, currency="USD", rooms_count=4, property_type="apartment")
    
    print("=== Тест 2: Объявление за 700 USD ===")
    print(f"Цена: {ad_700_usd.price} {ad_700_usd.currency}")
    
    for i, pf in enumerate(price_filters):
        matches = pf.matches_price(ad_700_usd.price, ad_700_usd.currency)
        print(f"Ценовой фильтр {i+1}: {pf.currency} max={pf.max_price} -> {matches}")
    
    matches = simple_filter.matches_with_price_filters(ad_700_usd, price_filters)
    print(f"Общий результат: {matches}")
    print()
    
    # Тест 3: Объявление без цены (должно пройти)
    ad_no_price = MockAd(price=None, currency=None, rooms_count=4, property_type="apartment")
    
    print("=== Тест 3: Объявление без цены ===")
    print(f"Цена: {ad_no_price.price} {ad_no_price.currency}")
    
    matches = simple_filter.matches_with_price_filters(ad_no_price, price_filters)
    print(f"Общий результат: {matches}")

if __name__ == "__main__":
    test_price_filtering()
