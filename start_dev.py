#!/usr/bin/env python3
"""
Development script for starting the application with ngrok
"""
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def check_ngrok_running():
    """Check if ngrok is already running"""
    try:
        response = requests.get("http://localhost:4040/api/tunnels", timeout=2)
        return response.status_code == 200
    except:
        return False


def get_ngrok_url():
    """Get the current ngrok URL"""
    try:
        response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
        if response.status_code == 200:
            data = response.json()
            tunnels = data.get("tunnels", [])

            # Find HTTPS tunnel first
            for tunnel in tunnels:
                if tunnel.get("proto") == "https" and tunnel.get("public_url"):
                    return tunnel["public_url"]

            # Fallback to HTTP tunnel
            for tunnel in tunnels:
                if tunnel.get("proto") == "http" and tunnel.get("public_url"):
                    return tunnel["public_url"]
    except Exception as e:
        print(f"Error getting ngrok URL: {e}")

    return None


def start_ngrok():
    """Start ngrok tunnel using shell script"""
    print("🚀 Starting ngrok tunnel...")

    # Check if ngrok is already running
    if check_ngrok_running():
        print("✅ Ngrok is already running")
        return True

    try:
        # Use the shell script to start ngrok
        result = subprocess.run(["./scripts/ngrok.sh", "start"], capture_output=True, text=True, cwd=os.getcwd())

        if result.returncode == 0:
            print("✅ Ngrok started successfully")
            return True
        else:
            print(f"❌ Failed to start ngrok: {result.stderr}")
            return False

    except FileNotFoundError:
        print("❌ Ngrok script not found. Please make sure scripts/ngrok.sh exists and is executable")
        return False
    except Exception as e:
        print(f"❌ Error starting ngrok: {e}")
        return False


def update_env_file(api_url):
    """Update .env file with the ngrok URL"""
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  .env file not found. Please create it first.")
        return False

    try:
        # Read current .env
        with open(env_file, "r") as f:
            lines = f.readlines()

        # Update or add API_BASE_URL
        updated = False
        for i, line in enumerate(lines):
            if line.startswith("API_BASE_URL="):
                lines[i] = f"API_BASE_URL={api_url}\n"
                updated = True
                break

        if not updated:
            lines.append(f"API_BASE_URL={api_url}\n")

        # Write back
        with open(env_file, "w") as f:
            f.writelines(lines)

        print(f"✅ Updated .env file with API_BASE_URL={api_url}")
        return True

    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        return False


def print_instructions(api_url, web_app_url):
    """Print setup instructions"""
    print("\n" + "=" * 60)
    print("🎉 SETUP COMPLETE!")
    print("=" * 60)
    print(f"📱 API URL: {api_url}")
    print(f"🌐 Web App URL: {web_app_url}")
    print("\n📋 Next steps:")
    print("1. Open @BotFather in Telegram")
    print("2. Send /newapp command")
    print("3. Select your bot")
    print("4. Use this URL:", web_app_url)
    print("5. Configure other settings and save")
    print("\n🔗 Test your Web App:")
    print(f"   {web_app_url}")
    print("\n📊 Monitor ngrok:")
    print("   http://localhost:4040")
    print("=" * 60)


def main():
    """Main function"""
    print("🏠 Telegram Real Estate Bot - Development Setup")
    print("=" * 50)

    # Check if .env exists
    if not Path(".env").exists():
        print("❌ .env file not found. Please create it first.")
        print("   Copy .env.example to .env and fill in your values.")
        sys.exit(1)

    # Start ngrok
    if not start_ngrok():
        sys.exit(1)

    # Wait for ngrok to be ready
    print("⏳ Waiting for ngrok to be ready...")
    for i in range(10):
        time.sleep(1)
        if check_ngrok_running():
            break
    else:
        print("❌ Ngrok failed to start properly")
        sys.exit(1)

    # Get ngrok URL
    api_url = get_ngrok_url()
    if not api_url:
        print("❌ Could not get ngrok URL")
        sys.exit(1)

    web_app_url = f"{api_url}/api/v1/static/search-settings"

    # Update .env file
    update_env_file(api_url)

    # Print instructions
    print_instructions(api_url, web_app_url)

    print("\n🚀 Starting application...")
    print("   Press Ctrl+C to stop")

    # Start the application
    try:
        subprocess.run(["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"])
    except KeyboardInterrupt:
        print("\n👋 Stopping application...")
    except Exception as e:
        print(f"❌ Error starting application: {e}")


if __name__ == "__main__":
    main()
