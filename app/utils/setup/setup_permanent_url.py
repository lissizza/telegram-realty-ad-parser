#!/usr/bin/env python3
"""
Script to set up permanent URL for ngrok and Telegram Web App
"""
import os
import sys
from pathlib import Path

def create_ngrok_config():
    """Create ngrok configuration file"""
    print("🔧 Setting up permanent ngrok URL...")
    
    # Get subdomain from user
    subdomain = input("Enter your preferred subdomain (e.g., 'rent-no-fees'): ").strip()
    if not subdomain:
        subdomain = "rent-no-fees"
        print(f"Using default subdomain: {subdomain}")
    
    # Get auth token
    auth_token = input("Enter your ngrok auth token (or press Enter to use from .env): ").strip()
    if not auth_token:
        # Try to get from .env
        env_file = Path(".env")
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith("NGROK_AUTHTOKEN="):
                        auth_token = line.split("=", 1)[1].strip()
                        break
        
        if not auth_token:
            print("❌ No auth token found. Please get one from https://dashboard.ngrok.com/get-started/your-authtoken")
            return False
    
    # Create ngrok.yml
    config_content = f"""# Ngrok configuration file
# This file provides a permanent URL for your Telegram Web App
# Auth token is read from NGROK_AUTHTOKEN environment variable

version: "2"
# Auth token will be read from NGROK_AUTHTOKEN environment variable
# Set it in your .env file or export it: export NGROK_AUTHTOKEN=your_token

tunnels:
  {subdomain}:
    proto: http
    addr: 8000
    subdomain: {subdomain}
    inspect: true
    web_addr: localhost:4040
    
  # Alternative tunnel without subdomain (for backup)
  {subdomain}-backup:
    proto: http
    addr: 8000
    inspect: true
    web_addr: localhost:4041
"""
    
    with open("ngrok.yml", "w") as f:
        f.write(config_content)
    
    print(f"✅ Created ngrok.yml with subdomain: {subdomain}")
    return subdomain

def update_env_file(subdomain):
    """Update .env file with permanent URL"""
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found. Please create it first.")
        return False
    
    permanent_url = f"https://{subdomain}.ngrok.io"
    
    try:
        # Read current .env
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Update or add API_BASE_URL
        updated = False
        for i, line in enumerate(lines):
            if line.startswith("API_BASE_URL="):
                lines[i] = f"API_BASE_URL={permanent_url}\n"
                updated = True
                break
        
        if not updated:
            lines.append(f"API_BASE_URL={permanent_url}\n")
        
        # Write back
        with open(env_file, 'w') as f:
            f.writelines(lines)
        
        print(f"✅ Updated .env file with API_BASE_URL={permanent_url}")
        return permanent_url
        
    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        return False

def print_instructions(subdomain, permanent_url):
    """Print setup instructions"""
    web_app_url = f"{permanent_url}/api/v1/static/search-settings"
    
    print("\n" + "="*70)
    print("🎉 PERMANENT URL SETUP COMPLETE!")
    print("="*70)
    print(f"🔗 Permanent URL: {permanent_url}")
    print(f"🌐 Web App URL: {web_app_url}")
    print(f"📝 Subdomain: {subdomain}")
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
    print("\n🚀 To start your app:")
    print("   python start_dev.py")
    print("="*70)

def main():
    """Main function"""
    print("🏠 Telegram Real Estate Bot - Permanent URL Setup")
    print("="*50)
    
    # Check if .env exists
    if not Path(".env").exists():
        print("❌ .env file not found. Please create it first.")
        print("   Copy .env.example to .env and fill in your values.")
        sys.exit(1)
    
    # Create ngrok config
    subdomain = create_ngrok_config()
    if not subdomain:
        sys.exit(1)
    
    # Update .env file
    permanent_url = update_env_file(subdomain)
    if not permanent_url:
        sys.exit(1)
    
    # Print instructions
    print_instructions(subdomain, permanent_url)

if __name__ == "__main__":
    main()
