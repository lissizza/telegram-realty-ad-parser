#!/usr/bin/env python3
"""
Скрипт для настройки аутентификации в Docker контейнере
"""
import asyncio
import os
import sys
from telethon import TelegramClient
from app.core.config import settings

async def setup_auth():
    """Настройка аутентификации"""
    print("🔐 Настройка аутентификации Telegram API в Docker...")
    
    client = TelegramClient(
        settings.TELEGRAM_SESSION_NAME,
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH
    )
    
    try:
        print("📱 Запуск клиента...")
        await client.start(phone=settings.TELEGRAM_PHONE)
        
        print("✅ Аутентификация успешна!")
        
        # Сохраняем сессию
        await client.disconnect()
        print("💾 Сессия сохранена")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(setup_auth())
    sys.exit(0 if success else 1)



