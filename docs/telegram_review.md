# Ревизия моделей Telegram

## Текущие модели и их назначение:

### 1. TelegramPost
**Текущее назначение**: Полученные сообщения из каналов
**Проблемы**:
- Поле `status: MessageStatus = MessageStatus.RECEIVED` указывает на получение
- Смешивает входящие сообщения с нашими постами
- Много полей для обработки, которые не нужны для наших постов

**Поля**:
- `id, channel_id, channel_title, message, date` - базовые данные сообщения
- `views, forwards, replies` - статистика (нужна только для входящих)
- `media_type, url` - медиа (нужно для входящих)
- `status, processed_at, parsing_errors` - обработка (нужно для входящих)
- `is_spam, spam_reason, is_real_estate, real_estate_confidence` - фильтрация (нужно для входящих)
- `forwarded, forwarded_at, forwarded_to` - пересылка (нужно для входящих)

### 2. RealEstateAd
**Назначение**: Распарсенные объявления недвижимости
**Статус**: ✅ Правильно настроена

### 3. ForwardedPost
**Назначение**: Пересланные посты пользователям
**Статус**: ✅ Правильно настроена

## Предлагаемая архитектура:

### 1. IncomingMessage (вместо TelegramPost)
**Назначение**: Входящие сообщения из каналов
**Поля**:
- `id, channel_id, channel_title, message, date` - базовые данные
- `views, forwards, replies` - статистика
- `media_type, url` - медиа
- `processing_status` - статус обработки (pending, processing, completed, failed)
- `parsing_errors` - ошибки парсинга
- `is_spam, spam_reason` - антиспам
- `is_real_estate, real_estate_confidence` - определение недвижимости
- `real_estate_ad_id` - ссылка на RealEstateAd
- `forwarded, forwarded_at, forwarded_to` - пересылка

### 2. OutgoingPost (новая модель)
**Назначение**: Наши посты, которые мы отправляем
**Поля**:
- `id` - уникальный ID
- `message` - текст сообщения
- `media_type, media_url` - медиа (если есть)
- `sent_at` - время отправки
- `sent_to` - кому отправлено (user_id, channel_id)
- `status` - статус отправки (pending, sent, failed)
- `error_message` - ошибка отправки
- `real_estate_ad_id` - ссылка на исходное объявление

### 3. RealEstateAd
**Статус**: ✅ Оставить как есть

### 4. ForwardedPost
**Статус**: ✅ Оставить как есть

## Действия:

1. Переименовать `TelegramPost` → `IncomingMessage`
2. Создать новую модель `OutgoingPost`
3. Обновить все ссылки на `TelegramPost`
4. Обновить сервисы для работы с новыми моделями
