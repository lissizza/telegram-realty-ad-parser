# Scripts for Architecture Diagrams

Этот каталог содержит скрипты для генерации архитектурных диаграмм проекта.

## Установка зависимостей

```bash
# Установка Python библиотеки diagrams
pip install diagrams

# Установка Graphviz (для рендеринга диаграмм)
# Ubuntu/Debian:
sudo apt-get install graphviz

# macOS:
brew install graphviz

# В Docker контейнере:
docker-compose exec app apt-get update && docker-compose exec app apt-get install -y graphviz
```

## Генерация диаграмм

### 1. Простая архитектурная диаграмма
```bash
docker-compose exec app python scripts/generate_simple_diagram.py
```
Создает файл `docs/simple_architecture.png` с общей схемой потока данных.

### 2. Диаграмма моделей данных
```bash
docker-compose exec app python scripts/generate_models_diagram.py
```
Создает файл `docs/models_diagram.png` с диаграммой моделей данных.

### 3. Полная архитектурная диаграмма
```bash
docker-compose exec app python scripts/generate_architecture_diagram.py
```
Создает файл `docs/architecture_diagram.png` с детальной архитектурой.

## Структура диаграмм

### Simple Architecture
- Показывает основной поток данных от Telegram канала до пользователей
- Включает компоненты: Telegram Bot, LLM Service, Filter Service, Queue Service
- Базы данных: MongoDB, Redis

### Models Diagram
- Показывает связи между моделями данных
- Включает: IncomingMessage, QueuedMessage, RealEstateAd, OutgoingPost, SimpleFilter
- Показывает поток обработки от входящего сообщения до отправки пользователю

## Настройка

Все диаграммы генерируются в формате PNG и сохраняются в каталог `docs/`.

Для изменения стиля или добавления новых компонентов отредактируйте соответствующие Python файлы в каталоге `scripts/`.
