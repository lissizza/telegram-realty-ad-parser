#!/bin/bash

# Ngrok management script
# Usage: ./scripts/ngrok.sh [start|stop|status|url|webapp-url]

set -e

NGROK_API_URL="http://localhost:4040/api"
NGROK_CONFIG_FILE="ngrok.yml"
NGROK_PORT="8001"
NGROK_SUBDOMAIN="rent-no-fees-filter"

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

# Check if ngrok is installed
check_ngrok_installed() {
    if ! command -v ngrok &> /dev/null; then
        log_error "Ngrok is not installed. Please install it first:"
        echo "  brew install ngrok  # macOS"
        echo "  or download from https://ngrok.com/"
        exit 1
    fi
}

# Check if ngrok is running
is_ngrok_running() {
    if curl -s --connect-timeout 2 "$NGROK_API_URL/tunnels" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Get ngrok URL
get_ngrok_url() {
    local response
    response=$(curl -s --connect-timeout 5 "$NGROK_API_URL/tunnels" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        # Try to get HTTPS URL first
        local https_url
        https_url=$(echo "$response" | jq -r '.tunnels[] | select(.proto == "https" and .public_url != null) | .public_url' 2>/dev/null | head -n1)
        
        if [ -n "$https_url" ] && [ "$https_url" != "null" ]; then
            echo "$https_url"
            return 0
        fi
        
        # Fallback to HTTP URL
        local http_url
        http_url=$(echo "$response" | jq -r '.tunnels[] | select(.proto == "http" and .public_url != null) | .public_url' 2>/dev/null | head -n1)
        
        if [ -n "$http_url" ] && [ "$http_url" != "null" ]; then
            echo "$http_url"
            return 0
        fi
    fi
    
    return 1
}

# Start ngrok
start_ngrok() {
    log_info "Starting ngrok tunnel..."
    
    if is_ngrok_running; then
        log_success "Ngrok is already running"
        return 0
    fi
    
    check_ngrok_installed
    
    # Check if config file exists
    if [ -f "$NGROK_CONFIG_FILE" ]; then
        log_info "Using ngrok configuration file: $NGROK_CONFIG_FILE"
        
        # Check if NGROK_AUTHTOKEN is set
        if [ -z "$NGROK_AUTHTOKEN" ]; then
            log_warning "NGROK_AUTHTOKEN not set. Using default configuration."
        else
            log_success "Using NGROK_AUTHTOKEN from environment"
        fi
        
        # Start ngrok with config file
        ngrok start rent-no-fees-filter --config "$NGROK_CONFIG_FILE" &
        local ngrok_pid=$!
        
    else
        log_info "Using command line configuration with subdomain: $NGROK_SUBDOMAIN"
        
        # Check if NGROK_AUTHTOKEN is set
        if [ -z "$NGROK_AUTHTOKEN" ]; then
            log_warning "NGROK_AUTHTOKEN not set. This may cause issues with subdomain usage."
        else
            log_success "Using NGROK_AUTHTOKEN from environment"
        fi
        
        # Start ngrok with subdomain
        ngrok http "$NGROK_PORT" --subdomain "$NGROK_SUBDOMAIN" &
        local ngrok_pid=$!
    fi
    
    # Wait for ngrok to start
    log_info "Waiting for ngrok to start..."
    local attempts=0
    while [ $attempts -lt 10 ]; do
        sleep 1
        if is_ngrok_running; then
            log_success "Ngrok started successfully (PID: $ngrok_pid)"
            return 0
        fi
        attempts=$((attempts + 1))
    done
    
    log_error "Failed to start ngrok after 10 seconds"
    return 1
}

# Stop ngrok
stop_ngrok() {
    log_info "Stopping ngrok..."
    
    if ! is_ngrok_running; then
        log_warning "Ngrok is not running"
        return 0
    fi
    
    # Find ngrok processes and kill them
    local pids
    pids=$(pgrep -f "ngrok" || true)
    
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -TERM 2>/dev/null || true
        sleep 2
        echo "$pids" | xargs kill -KILL 2>/dev/null || true
        log_success "Ngrok stopped"
    else
        log_warning "No ngrok processes found"
    fi
}

# Get ngrok status
get_status() {
    if is_ngrok_running; then
        log_success "Ngrok is running"
        
        local url
        if url=$(get_ngrok_url); then
            echo "URL: $url"
            echo "Web App URL: $url/api/v1/static/search-settings"
            echo "Web Interface: http://localhost:4040"
        else
            log_warning "Could not get ngrok URL"
        fi
    else
        log_warning "Ngrok is not running"
        return 1
    fi
}

# Get ngrok URL only
get_url() {
    if is_ngrok_running; then
        if url=$(get_ngrok_url); then
            echo "$url"
        else
            log_error "Could not get ngrok URL"
            exit 1
        fi
    else
        log_error "Ngrok is not running"
        exit 1
    fi
}

# Get web app URL
get_webapp_url() {
    if is_ngrok_running; then
        if url=$(get_ngrok_url); then
            echo "$url/api/v1/static/search-settings"
        else
            log_error "Could not get ngrok URL"
            exit 1
        fi
    else
        log_error "Ngrok is not running"
        exit 1
    fi
}

# Main function
main() {
    case "${1:-status}" in
        start)
            start_ngrok
            ;;
        stop)
            stop_ngrok
            ;;
        status)
            get_status
            ;;
        url)
            get_url
            ;;
        webapp-url)
            get_webapp_url
            ;;
        *)
            echo "Usage: $0 [start|stop|status|url|webapp-url]"
            echo ""
            echo "Commands:"
            echo "  start       - Start ngrok tunnel"
            echo "  stop        - Stop ngrok tunnel"
            echo "  status      - Show ngrok status and URLs"
            echo "  url         - Get ngrok tunnel URL only"
            echo "  webapp-url  - Get web app URL for Telegram"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
















