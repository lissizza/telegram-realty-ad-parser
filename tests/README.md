# LLM Parsing Tests

Этот каталог содержит unit тесты и интеграционные тесты для проверки парсинга объявлений недвижимости с помощью LLM.

## Структура тестов

### Unit тесты (с мокированием)

#### `test_llm_unit_simple.py`
Простые unit тесты для проверки парсинга различных типов объявлений:

- **test_llm_parsing_basic_apartment** - Тест парсинга базовой квартиры с основными полями
- **test_llm_parsing_studio** - Тест парсинга студии (должна определяться как 1-комнатная квартира)
- **test_llm_parsing_house** - Тест парсинга дома
- **test_llm_parsing_detailed_apartment** - Тест парсинга детального объявления со всеми возможными полями
- **test_llm_parsing_non_real_estate** - Тест определения не-недвижимости (должен возвращать None)

#### `test_llm_unit.py`
Расширенные unit тесты для проверки различных аспектов парсинга:
- **test_llm_parsing_basic_fields** - Тест базовых полей
- **test_llm_parsing_address_extraction** - Тест извлечения адресов
- **test_llm_parsing_room_count_variations** - Тест различных форматов указания комнат
- **test_llm_parsing_price_currencies** - Тест парсинга цен и валют
- **test_llm_parsing_boolean_features** - Тест извлечения булевых характеристик
- **test_llm_parsing_contact_extraction** - Тест извлечения контактов
- **test_llm_parsing_non_real_estate** - Тест определения не-недвижимости

### Интеграционные тесты (реальные вызовы LLM)

#### `test_llm_integration.py`
Настоящие интеграционные тесты, которые делают реальные запросы к LLM API:
- **test_real_llm_parsing_apartment** - Реальный тест парсинга квартиры
- **test_real_llm_parsing_studio** - Реальный тест парсинга студии
- **test_real_llm_parsing_house** - Реальный тест парсинга дома
- **test_real_llm_parsing_detailed_apartment** - Реальный тест детального объявления
- **test_real_llm_parsing_non_real_estate** - Реальный тест не-недвижимости
- **test_real_llm_parsing_ambiguous_cases** - Тест неоднозначных случаев

## Запуск тестов

### Unit тесты (быстрые)
```bash
# Все unit тесты
docker-compose exec app python -m pytest tests/test_llm_unit*.py -v

# Только простые unit тесты
docker-compose exec app python -m pytest tests/test_llm_unit_simple.py -v

# Конкретный тест
docker-compose exec app python -m pytest tests/test_llm_unit_simple.py::TestLLMParsingSimple::test_llm_parsing_basic_apartment -v
```

### Интеграционные тесты (медленные)
```bash
# Все интеграционные тесты (реальные вызовы LLM)
docker-compose exec app python -m pytest tests/test_llm_integration.py -v

# Только быстрые тесты (исключить интеграционные)
docker-compose exec app python -m pytest -m "not slow" -v

# С подробным выводом
docker-compose exec app python -m pytest tests/test_llm_integration.py -v -s
```

## Тестовые данные

Тесты используют реальные примеры объявлений из Telegram каналов:

1. **2-комнатная квартира** - базовый пример с адресом, ценой, разрешением на животных
2. **Однокомнатная квартира** - студия с адресом и ценой
3. **Дом** - дом с 3 комнатами, парковкой и районом
4. **Детальная квартира** - полный пример со всеми возможными полями (этаж, площадь, контакты, удобства)

## Мокирование

Тесты используют `unittest.mock.patch` для мокирования вызовов к LLM API:

```python
with patch.object(llm_service, '_call_llm') as mock_llm:
    mock_llm.return_value = {
        "response": json.dumps(mock_response),
        "cost_info": {
            "prompt_tokens": 50,
            "completion_tokens": 50,
            "total_tokens": 100,
            "cost_usd": 0.01,
            "model_name": "gpt-3.5-turbo"
        }
    }
```

## Проверяемые поля

Тесты проверяют корректность парсинга следующих полей:

### Основные поля
- `is_real_estate` - является ли объявление недвижимостью
- `property_type` - тип недвижимости (apartment, house, room)
- `rental_type` - тип аренды (long_term, daily)
- `rooms_count` - количество комнат
- `area_sqm` - площадь в квадратных метрах
- `price_amd` - цена в драмах
- `price_usd` - цена в долларах

### Локация
- `address` - адрес
- `district` - район
- `city` - город

### Удобства
- `has_balcony` - балкон
- `has_air_conditioning` - кондиционер
- `has_internet` - интернет
- `has_furniture` - мебель
- `has_parking` - парковка
- `has_garden` - сад
- `has_pool` - бассейн
- `pets_allowed` - разрешены ли животные
- `utilities_included` - включены ли коммунальные услуги

### Дополнительная информация
- `floor` - этаж
- `total_floors` - общее количество этажей
- `contacts` - контактная информация
- `additional_notes` - дополнительные заметки
- `parsing_confidence` - уверенность парсинга

## Добавление новых тестов

Для добавления нового теста:

1. Создайте новый метод в классе `TestLLMParsingSimple`
2. Используйте декоратор `@pytest.mark.asyncio`
3. Создайте тестовый текст объявления
4. Настройте мок-ответ LLM
5. Проверьте ожидаемые поля в результате

Пример:

```python
@pytest.mark.asyncio
async def test_llm_parsing_new_case(self, llm_service):
    """Test new parsing case"""
    test_text = "Ваш тестовый текст объявления"
    
    with patch.object(llm_service, '_call_llm') as mock_llm:
        mock_response = {
            "is_real_estate": True,
            "parsing_confidence": 0.8,
            # ... другие поля
        }
        
        mock_llm.return_value = {
            "response": json.dumps(mock_response),
            "cost_info": {
                "prompt_tokens": 50,
                "completion_tokens": 50,
                "total_tokens": 100,
                "cost_usd": 0.01,
                "model_name": "gpt-3.5-turbo"
            }
        }
        
        result = await llm_service.parse_with_llm(test_text, post_id=1, channel_id=12345)
        
        # Проверки
        assert result is not None
        assert result.property_type == PropertyType.APARTMENT
        # ... другие проверки
```

## Отладка тестов

Если тест не проходит:

1. Проверьте, что все необходимые поля присутствуют в модели `RealEstateAd`
2. Убедитесь, что мок-данные соответствуют ожидаемому формату
3. Проверьте, что значения enum'ов соответствуют определенным в модели
4. Используйте `-s` флаг для вывода print statements
5. Проверьте логи приложения на наличие ошибок
