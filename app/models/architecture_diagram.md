# Архитектура моделей Telegram

## Обзор

После ревизии мы разделили модели по их назначению:

## Модели данных

### 1. IncomingMessage
**Назначение**: Входящие сообщения из Telegram каналов
**Поля**:
- `id, channel_id, channel_title, message, date` - базовые данные
- `views, forwards, replies` - статистика Telegram
- `media_type, media_url` - медиа контент
- `processing_status` - статус обработки (pending, processing, completed, failed)
- `is_spam, spam_reason` - антиспам фильтрация
- `is_real_estate, real_estate_confidence` - определение недвижимости
- `real_estate_ad_id` - ссылка на распарсенное объявление
- `forwarded, forwarded_at, forwarded_to` - информация о пересылке

### 2. RealEstateAd
**Назначение**: Распарсенные объявления недвижимости
**Поля**:
- `original_post_id, original_channel_id, original_message` - исходные данные
- `property_type, rental_type, rooms_count, area_sqm` - основные характеристики
- `price, currency` - цена и валюта (универсальные поля)
- `district, address, city` - местоположение
- `has_balcony, has_air_conditioning, has_elevator, pets_allowed` - особенности
- `processing_status, llm_processed, llm_cost` - статус обработки
- `matched_filters, should_forward` - результаты фильтрации

### 3. OutgoingPost
**Назначение**: Сообщения, которые мы отправляем пользователям
**Поля**:
- `message` - текст сообщения
- `media_type, media_url` - медиа контент
- `sent_to, sent_to_type` - кому отправлено (user/channel)
- `status` - статус отправки (pending, sent, failed)
- `real_estate_ad_id` - ссылка на исходное объявление

### 4. QueuedMessage
**Назначение**: Сообщения в очереди обработки Redis
**Поля**:
- `original_post_id, original_channel_id, original_message` - исходные данные
- `status` - статус обработки (pending, processing, completed, failed)
- `llm_processed, llm_cost` - результаты LLM обработки
- `parsed_data` - распарсенные данные

### 5. SimpleFilter
**Назначение**: Фильтры пользователей для отбора объявлений
**Поля**:
- `property_types, rental_types` - типы недвижимости
- `min_rooms, max_rooms, min_area, max_area` - размеры
- `min_price, max_price, price_currency` - цена и валюта
- `districts` - районы
- `has_balcony, has_air_conditioning, has_elevator` - особенности

## Поток обработки

```
1. Telegram Channel
   ↓
2. IncomingMessage (получено сообщение)
   ↓
3. QueuedMessage (добавлено в очередь Redis)
   ↓
4. LLM Processing (парсинг через OpenAI)
   ↓
5. RealEstateAd (сохранено в базу)
   ↓
6. Filter Matching (проверка по SimpleFilter)
   ↓
7. OutgoingPost (отправка пользователю)
```

## Ключевые принципы

1. **Разделение ответственности**: Каждая модель имеет четкое назначение
2. **Сохранение всех данных**: Все результаты LLM сохраняются в базу
3. **Очередь обработки**: Redis очередь предотвращает потерю сообщений
4. **Статусы обработки**: Отслеживание состояния каждого сообщения
5. **Универсальные поля**: `price`/`currency` вместо `price_amd`/`price_usd`

## Удаленные модели

- **TelegramPost** - заменена на IncomingMessage и OutgoingPost
- **MessageStatus** - заменен на строковые статусы в каждой модели
