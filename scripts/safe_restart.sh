#!/bin/bash

# Safe restart script - restarts containers without losing data
echo "🔄 Safe restart of Docker containers..."

# Stop containers gracefully
echo "⏹️  Stopping containers..."
docker-compose stop

# Start containers
echo "▶️  Starting containers..."
docker-compose up -d

echo "✅ Safe restart completed. Data preserved."
echo "⚠️  To completely reset (DANGER - will lose data): docker-compose down -v"
