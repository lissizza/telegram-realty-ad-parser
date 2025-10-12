# Telegram Realty Ad Parser 🏠

[![Hacktoberfest](https://img.shields.io/badge/Hacktoberfest-2025-orange.svg)](https://hacktoberfest.com/)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)](https://fastapi.tiangolo.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-green.svg)](https://www.mongodb.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A Telegram bot that monitors real estate channels, parses advertisements using LLM, and forwards relevant posts based on user-defined filters. The system uses a centralized channel management approach where administrators control which channels are monitored, while users create personal filters to receive relevant advertisements.

## 🎃 Hacktoberfest 2025

This project participates in Hacktoberfest! We welcome contributions from the community. Check out our [Contributing Guide](CONTRIBUTING.md) to get started.

## Features

- **Real Estate Parsing**: Automatically extracts structured data from real estate advertisements using LLM
- **Smart Filtering**: User-configurable filters based on property type, price, location, and more
- **Centralized Channel Management**: Administrators manage monitored channels, users only manage their filters
- **Role-Based Access Control**: Admin panel with different permission levels
- **MongoDB Storage**: Stores all posts and parsed data for analysis
- **REST API**: FastAPI-based API for managing filters and viewing data
- **Web Interface**: User-friendly web interface for filter and channel management
- **Docker Support**: Complete containerized setup with Docker Compose

## Extracted Data

The bot parses the following information from real estate advertisements:

- **Property Type**: Apartment, House, Room, Hotel Room
- **Rental Type**: Long-term or Daily rental
- **Rooms Count**: Number of bedrooms
- **Area**: Square meters
- **Price**: In AMD (Armenian Dram) and USD
- **District**: Location within Yerevan
- **Address**: Street address
- **Contacts**: Phone numbers and Telegram usernames
- **Features**: Balcony, Air conditioning, Internet, Furniture, etc.

## Architecture

The system follows a centralized channel management approach:

### User Roles

- **Users**: Can create and manage personal filters to receive relevant advertisements
- **Administrators**: Can manage monitored channels, view statistics, and manage users
- **Super Administrators**: Full system access including admin management

### System Flow

1. **Channel Monitoring**: Administrators add channels to the monitoring list
2. **Message Processing**: All messages from monitored channels are parsed by LLM
3. **Filter Application**: Each parsed advertisement is checked against all user filters
4. **Message Forwarding**: Matching advertisements are forwarded to respective users

### Project Structure

```
├── app/
│   ├── api/v1/endpoints/     # REST API endpoints
│   ├── bot/                  # Telegram bot commands and callbacks
│   ├── core/                 # Configuration and core utilities
│   ├── db/                   # Database connection and utilities
│   ├── models/               # Pydantic data models
│   ├── services/             # Business logic services
│   └── static/               # Web interface files
├── docker-compose.yml        # Docker orchestration
├── Dockerfile               # Application container
└── pyproject.toml          # Python dependencies
```

## Quick Start

### Prerequisites

1. **Telegram API Credentials**: Get your API ID and Hash from [my.telegram.org](https://my.telegram.org)
2. **Docker and Docker Compose**: Install Docker and Docker Compose

### Setup

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd telegram-real-estate-bot
   ```

2. **Configure environment**:

   ```bash
   cp env.example .env
   # Edit .env with your Telegram API credentials
   ```

3. **Start the application**:

   ```bash
   docker-compose up -d
   ```

4. **Access the system**:

   - API Documentation: http://localhost:8001/docs
   - Health Check: http://localhost:8001/health
   - MongoDB Express: http://localhost:8081
   - Web Interface: http://localhost:8001/api/v1/static/simple-filters?user_id=YOUR_USER_ID

5. **Set up admin user**:
   ```bash
   # Create super admin (run inside Docker container)
   docker-compose exec app python app/utils/setup/create_super_admin.py YOUR_TELEGRAM_USER_ID
   ```

### Environment Variables

| Variable                      | Description                               | Required |
| ----------------------------- | ----------------------------------------- | -------- |
| `TELEGRAM_API_ID`             | Your Telegram API ID                      | Yes      |
| `TELEGRAM_API_HASH`           | Your Telegram API Hash                    | Yes      |
| `TELEGRAM_PHONE`              | Your phone number                         | Yes      |
| `TELEGRAM_BOT_TOKEN`          | Bot token (optional)                      | No       |
| `SECRET_KEY`                  | Secret key for JWT tokens                 | Yes      |
| `MONGODB_URL`                 | MongoDB connection string                 | Yes      |
| `REDIS_URL`                   | Redis connection string                   | Yes      |
| `DEFAULT_MONITORED_CHANNEL`   | Channel ID to monitor for real estate ads | Yes      |
| `FORWARDING_CHANNEL`          | Channel for forwarding filtered ads       | Yes      |
| `TELEGRAM_MONITORED_CHANNELS` | Additional channels to monitor (optional) | No       |
| `LLM_API_KEY`                 | API key for LLM service (optional)        | No       |

### Environment Examples

**Development (.env):**

```env
# Secrets
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+374123456789
SECRET_KEY=dev-secret-key

# Database (Docker)
MONGODB_URL=mongodb://admin:password@mongo:27017/telegram_bot
REDIS_URL=redis://redis:6379

# Channels
DEFAULT_MONITORED_CHANNEL=-1001827102719
FORWARDING_CHANNEL=@real_estate_yerevan
TELEGRAM_MONITORED_CHANNELS=-1001827102719

# LLM Settings
ENABLE_LLM_PARSING=true
LLM_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=gpt-3.5-turbo
```

**Production (.env):**

```env
# Secrets
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+374123456789
SECRET_KEY=super-secure-production-key

# Database (external)
MONGODB_URL=mongodb://username:password@mongodb.example.com:27017/telegram_bot
REDIS_URL=redis://username:password@redis.example.com:6379

# Channels
DEFAULT_MONITORED_CHANNEL=-1001827102719
FORWARDING_CHANNEL=@real_estate_yerevan
TELEGRAM_MONITORED_CHANNELS=-1001827102719,-1001234567891

# LLM Settings
ENABLE_LLM_PARSING=true
LLM_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=gpt-3.5-turbo
```

## API Endpoints

### User Filters (Personal)

- `GET /api/v1/simple-filters/user/{user_id}` - Get user's filters
- `POST /api/v1/simple-filters/` - Create new filter
- `GET /api/v1/simple-filters/{id}` - Get specific filter
- `PUT /api/v1/simple-filters/{id}` - Update filter
- `DELETE /api/v1/simple-filters/{id}` - Delete filter

### Price Filters

- `GET /api/v1/price-filters/filter/{filter_id}` - Get price filters for a filter
- `POST /api/v1/price-filters/` - Create new price filter
- `PUT /api/v1/price-filters/{id}` - Update price filter
- `DELETE /api/v1/price-filters/{id}` - Delete price filter

### Monitored Channels (Admin Only)

- `GET /api/v1/monitored-channels/` - List all monitored channels
- `POST /api/v1/monitored-channels/` - Add new channel (admin only)
- `GET /api/v1/monitored-channels/{id}` - Get specific channel
- `PUT /api/v1/monitored-channels/{id}` - Update channel
- `DELETE /api/v1/monitored-channels/{id}` - Remove channel
- `POST /api/v1/monitored-channels/{id}/toggle-active` - Toggle channel status

### Admin Management

- `GET /api/v1/admin/check-rights?user_id={id}` - Check user admin rights
- `GET /api/v1/admin/users/` - List all admin users
- `POST /api/v1/admin/users/` - Create admin user
- `PUT /api/v1/admin/users/{id}` - Update admin user

### Real Estate Ads

- `GET /api/v1/real-estate-ads/` - List parsed advertisements
- `GET /api/v1/real-estate-ads/{id}` - Get specific advertisement
- `DELETE /api/v1/real-estate-ads/{id}` - Delete advertisement

### Web Interface

- `GET /api/v1/static/simple-filters?user_id={id}` - Filter management interface
- `GET /api/v1/static/channel-subscriptions?user_id={id}` - Channel management interface (admin only)

## Filter Configuration

### Simple Filters

Users can create personal filters with the following criteria:

- **Property Types**: apartment, house, room, hotel_room
- **Rental Types**: long_term, daily
- **Rooms Count**: min/max number of rooms
- **Area Range**: min/max square meters
- **Districts**: List of Yerevan districts
- **Keywords**: Must contain at least one keyword
- **Exclude Keywords**: Must not contain any excluded keywords
- **Features**: Balcony, air conditioning, internet, furniture, etc.

### Price Filters

Each simple filter can have multiple price filters:

- **Price Range**: min/max price in specific currency
- **Currency**: AMD, USD, or other supported currencies
- **Multiple Ranges**: Support for multiple price ranges per filter

### Filter Logic

- **AND Logic**: All specified criteria must match
- **OR Logic**: For price filters (if any price filter matches, the filter matches)
- **Null Values**: Null values mean "don't care" (no restriction)

## Development

### Local Development

1. **Install Poetry**:

   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Install dependencies**:

   ```bash
   poetry install
   ```

3. **Run the application**:
   ```bash
   poetry run uvicorn app.main:app --reload
   ```

### Testing

```bash
poetry run pytest
```

### Code Formatting

```bash
poetry run black .
poetry run isort .
```

## User Roles and Permissions

### User Roles

- **USER**: Can create and manage personal filters, view their forwarded messages
- **MODERATOR**: Can manage channels, view statistics, view logs
- **ADMIN**: Can manage users, channels, view statistics, manage settings
- **SUPER_ADMIN**: Full system access including admin management

### Permissions

- **MANAGE_CHANNELS**: Add, remove, and manage monitored channels
- **MANAGE_USERS**: Promote/demote users, manage user accounts
- **VIEW_STATS**: Access system statistics and analytics
- **VIEW_LOGS**: View system logs and monitoring data
- **MANAGE_ADMINS**: Create and manage admin users
- **MANAGE_SETTINGS**: Modify system settings and configuration

## Database Schema

### Collections

- **incoming_messages**: Original Telegram messages from monitored channels
- **real_estate_ads**: Parsed real estate advertisements with structured data
- **simple_filters**: User-defined filtering rules for advertisements
- **price_filters**: Price range filters associated with simple filters
- **outgoing_posts**: Records of forwarded posts to users
- **monitored_channels**: Channels monitored by the system (admin-managed)
- **admin_users**: Admin users with roles and permissions
- **user_filter_matches**: Records of filter matches for analytics
- **llm_costs**: LLM API usage tracking and costs

## Usage Guide

### For Regular Users

1. **Start the bot**: Send `/start` to the Telegram bot
2. **Create filters**: Use the "⚙️ Настроить фильтры" button to access the web interface
3. **View channels**: Use "📺 Список каналов" to see monitored channels
4. **Check statistics**: Use "📊 Статистика" to view your filter performance

### For Administrators

1. **Access admin panel**: Use "🔧 Админка" button in the bot
2. **Manage channels**: Use "📺 Управление каналами" to add/remove channels
3. **Manage users**: Use "👥 Управление пользователями" to promote/demote users
4. **View statistics**: Use "📊 Статистика" to see system-wide analytics

### Web Interface

- **Filter Management**: `http://localhost:8001/api/v1/static/simple-filters?user_id=YOUR_USER_ID`
- **Channel Management**: `http://localhost:8001/api/v1/static/channel-subscriptions?user_id=YOUR_USER_ID` (admin only)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License
