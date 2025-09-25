# Ngrok Setup Guide

This document explains how to use ngrok with the Telegram Real Estate Bot.

## Overview

We've simplified the ngrok setup by replacing the Python `ngrok_service.py` with shell scripts. This approach is more reliable and easier to manage.

## Files

- `scripts/ngrok.sh` - Main ngrok management script
- `scripts/start_with_ngrok.sh` - Docker startup script with ngrok
- `app/utils/ngrok.py` - Simple Python utilities for ngrok API
- `ngrok.yml` - Ngrok configuration file

## Usage

### Development (Local)

1. **Start ngrok manually:**
   ```bash
   ./scripts/ngrok.sh start
   ```

2. **Check status:**
   ```bash
   ./scripts/ngrok.sh status
   ```

3. **Get URL:**
   ```bash
   ./scripts/ngrok.sh url
   ```

4. **Get Web App URL:**
   ```bash
   ./scripts/ngrok.sh webapp-url
   ```

5. **Stop ngrok:**
   ```bash
   ./scripts/ngrok.sh stop
   ```

### Docker

The Docker container automatically starts ngrok when the application starts:

```bash
docker-compose up
```

Make sure to set `NGROK_AUTHTOKEN` in your `.env` file:

```env
NGROK_AUTHTOKEN=your_ngrok_auth_token_here
```

## Configuration

### ngrok.yml

The `ngrok.yml` file contains the ngrok configuration:

```yaml
version: "2"
tunnels:
  rent-no-fees-filter:
    proto: http
    addr: 8001
    subdomain: rent-no-fees-filter
    inspect: true
    web_addr: localhost:4040
```

### Environment Variables

- `NGROK_AUTHTOKEN` - Your ngrok auth token (required for subdomains)
- `API_BASE_URL` - Automatically set by the scripts
- `WEB_APP_URL` - Automatically set by the scripts

## API Endpoints

The following API endpoints are available:

- `GET /api/v1/ngrok/status` - Get ngrok status and tunnel information
- `GET /api/v1/ngrok/url` - Get the current ngrok URL
- `GET /api/v1/ngrok/webapp-url` - Get the Web App URL for Telegram
- `GET /api/v1/ngrok/config` - Get ngrok configuration and instructions

## Troubleshooting

### Ngrok not starting

1. Check if ngrok is installed:
   ```bash
   ngrok version
   ```

2. Check if NGROK_AUTHTOKEN is set:
   ```bash
   echo $NGROK_AUTHTOKEN
   ```

3. Check ngrok logs:
   ```bash
   ./scripts/ngrok.sh status
   ```

### Subdomain conflicts

If you get subdomain conflicts, either:
1. Use a different subdomain in `ngrok.yml`
2. Remove the subdomain to get a random URL
3. Use the backup tunnel configuration

### Port conflicts

Make sure port 8001 is available and not used by other services.

## Benefits of Shell Script Approach

1. **Simpler**: No complex Python service to maintain
2. **More reliable**: Direct ngrok process management
3. **Better error handling**: Clear error messages and status codes
4. **Easier debugging**: Direct access to ngrok logs
5. **Docker-friendly**: Works seamlessly in containers
6. **Cross-platform**: Works on Linux, macOS, and Windows (with WSL)

## Migration from ngrok_service.py

The old `ngrok_service.py` has been removed. All functionality is now available through:

1. Shell scripts for management
2. Simple Python utilities in `app/utils/ngrok.py`
3. Updated API endpoints

No code changes are needed in your application - the API endpoints remain the same.















