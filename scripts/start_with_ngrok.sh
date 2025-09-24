#!/bin/bash

# Start application with ngrok in Docker
# This script starts ngrok in the background and then starts the application

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to cleanup on exit
cleanup() {
    log_info "Shutting down..."
    if [ -n "$NGROK_PID" ]; then
        log_info "Stopping ngrok (PID: $NGROK_PID)..."
        kill $NGROK_PID 2>/dev/null || true
    fi
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Check if ngrok is available
if ! command -v ngrok &> /dev/null; then
    log_error "Ngrok is not installed in the container"
    exit 1
fi

# Check if NGROK_AUTHTOKEN is set
if [ -z "$NGROK_AUTHTOKEN" ]; then
    log_warning "NGROK_AUTHTOKEN not set. Ngrok may not work properly."
fi

# Start ngrok in background
log_info "Starting ngrok tunnel..."
if [ -f "ngrok.yml" ]; then
    log_info "Using ngrok configuration file"
    ngrok start rent-no-fees-filter --config ngrok.yml &
else
    log_info "Using default ngrok configuration"
    ngrok http 8001 --subdomain rent-no-fees-filter &
fi

NGROK_PID=$!
log_success "Ngrok started (PID: $NGROK_PID)"

# Wait for ngrok to be ready
log_info "Waiting for ngrok to be ready..."
for i in {1..10}; do
    if curl -s --connect-timeout 2 "http://localhost:4040/api/tunnels" > /dev/null 2>&1; then
        log_success "Ngrok is ready"
        break
    fi
    sleep 1
done

# Get ngrok URL and update environment
log_info "Getting ngrok URL..."
NGROK_URL=$(curl -s "http://localhost:4040/api/tunnels" | jq -r '.tunnels[] | select(.proto == "https" and .public_url != null) | .public_url' | head -n1)

if [ -z "$NGROK_URL" ] || [ "$NGROK_URL" = "null" ]; then
    NGROK_URL=$(curl -s "http://localhost:4040/api/tunnels" | jq -r '.tunnels[] | select(.proto == "http" and .public_url != null) | .public_url' | head -n1)
fi

if [ -n "$NGROK_URL" ] && [ "$NGROK_URL" != "null" ]; then
    log_success "Ngrok URL: $NGROK_URL"
    export API_BASE_URL="$NGROK_URL"
    export WEB_APP_URL="$NGROK_URL/api/v1/static/search-settings"
    log_info "Environment variables set:"
    log_info "  API_BASE_URL=$API_BASE_URL"
    log_info "  WEB_APP_URL=$WEB_APP_URL"
else
    log_warning "Could not get ngrok URL"
fi

# Start the application
log_info "Starting application..."
exec poetry run uvicorn app.main:app --host 0.0.0.0 --port 8001

