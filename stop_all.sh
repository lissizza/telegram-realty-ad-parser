#!/bin/bash

# Stop all Python processes
echo "Stopping all Python processes..."

# Kill Python processes
pkill -f python 2>/dev/null || true
pkill -f uvicorn 2>/dev/null || true

# Force kill if needed
sleep 2
pkill -9 -f python 2>/dev/null || true
pkill -9 -f uvicorn 2>/dev/null || true

# Wait a moment
sleep 2

# Check if any processes are still running
echo "Checking for remaining processes..."
ps aux | grep -E "(python|uvicorn)" | grep -v grep || echo "No Python processes found"

echo "All processes stopped!"
