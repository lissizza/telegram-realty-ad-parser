# Утилиты проекта

Этот каталог содержит вспомогательные скрипты и утилиты для проекта.

## Структура

### `telegram/` - Утилиты для работы с Telegram

- `get_user_id.py` - Получение User ID пользователя Telegram
- `get_channel_info.py` - Получение информации о каналах
- `get_subchannel_id.py` - Поиск подканалов по ключевым словам

### `setup/` - Скрипты настройки

- `create_session.py` - Создание сессии Telegram
- `manual_auth_setup.py` - Ручная настройка аутентификации
- `setup_auth_docker.py` - Настройка аутентификации в Docker
- `setup_permanent_url.py` - Настройка постоянного URL для ngrok
- `setup_telegram_auth.py` - Настройка аутентификации Telegram API
- `start_dev.py` - Запуск приложения в режиме разработки
- `update_ngrok_url.py` - Обновление ngrok URL в .env
- `migrate_message_status.py` - Миграция статусов сообщений

### `testing/` - Тестовые утилиты

- `test_api_endpoint.py` - Тестирование API endpoints
- `test_serialization.py` - Тестирование сериализации
- `test_subscriptions.py` - Тестирование сервиса подписок
- `find_processes.py` - Поиск и завершение Python процессов

## Использование

Все скрипты можно запускать из корня проекта:

```bash
# Получение User ID
python -m app.utils.telegram.get_user_id

# Настройка аутентификации
python -m app.utils.setup.setup_telegram_auth

# Запуск в режиме разработки
python -m app.utils.setup.start_dev

# Тестирование API
python -m app.utils.testing.test_api_endpoint
```

## Примечания

- Все скрипты используют настройки из `app.core.config`
- Для работы с Telegram требуется корректная настройка API_ID, API_HASH и номера телефона
- Тестовые скрипты создают логи в корне проекта
