# Telegram Real Estate Bot

A Telegram bot that monitors real estate channels, parses advertisements, and forwards relevant posts based on configurable filters.

## Features

- **Real Estate Parsing**: Automatically extracts structured data from real estate advertisements
- **Smart Filtering**: Configurable filters based on property type, price, location, and more
- **MongoDB Storage**: Stores all posts and parsed data for analysis
- **REST API**: FastAPI-based API for managing filters and viewing data
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

```
├── app/
│   ├── api/v1/endpoints/     # REST API endpoints
│   ├── core/                 # Configuration and core utilities
│   ├── db/                   # Database connection and utilities
│   ├── models/               # Pydantic data models
│   └── services/             # Business logic services
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

4. **Access the API**:
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health
   - MongoDB Express: http://localhost:8081

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_API_ID` | Your Telegram API ID | Yes |
| `TELEGRAM_API_HASH` | Your Telegram API Hash | Yes |
| `TELEGRAM_PHONE` | Your phone number | Yes |
| `TELEGRAM_BOT_TOKEN` | Bot token (optional) | No |
| `SECRET_KEY` | Secret key for JWT tokens | Yes |
| `MONGODB_URL` | MongoDB connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `DEFAULT_MONITORED_CHANNEL` | Channel ID to monitor for real estate ads | Yes |
| `FORWARDING_CHANNEL` | Channel for forwarding filtered ads | Yes |
| `TELEGRAM_MONITORED_CHANNELS` | Additional channels to monitor (optional) | No |
| `LLM_API_KEY` | API key for LLM service (optional) | No |

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

### Filters
- `GET /api/v1/filters/` - List all filters
- `POST /api/v1/filters/` - Create new filter
- `GET /api/v1/filters/{id}` - Get specific filter
- `PUT /api/v1/filters/{id}` - Update filter
- `DELETE /api/v1/filters/{id}` - Delete filter

### Posts
- `GET /api/v1/posts/` - List posts with pagination
- `GET /api/v1/posts/{id}` - Get specific post
- `DELETE /api/v1/posts/{id}` - Delete post

### Channels
- `GET /api/v1/channels/` - List monitored channels
- `POST /api/v1/channels/` - Add new channel
- `PUT /api/v1/channels/{id}` - Update channel
- `DELETE /api/v1/channels/{id}` - Remove channel

### Telegram Bot
- `POST /api/v1/telegram/start-monitoring` - Start monitoring
- `POST /api/v1/telegram/stop-monitoring` - Stop monitoring
- `GET /api/v1/telegram/status` - Get bot status

## Filter Configuration

Filters support the following criteria:

- **Property Types**: apartment, house, room, hotel_room
- **Rental Types**: long_term, daily
- **Price Range**: min/max in AMD or USD
- **Rooms Count**: min/max number of rooms
- **Area Range**: min/max square meters
- **Districts**: List of Yerevan districts
- **Keywords**: Must contain at least one keyword
- **Exclude Keywords**: Must not contain any excluded keywords

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

## Database Schema

### Collections

- **posts**: Original Telegram posts
- **real_estate_ads**: Parsed real estate advertisements
- **filters**: User-defined filtering rules
- **forwarded_posts**: Records of forwarded posts
- **channels**: Monitored Telegram channels

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License 