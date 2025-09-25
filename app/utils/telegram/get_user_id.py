#!/usr/bin/env python3
"""
Скрипт для получения вашего Telegram User ID
"""
import asyncio
from telethon import TelegramClient
from app.core.config import settings

async def get_user_id():
    """Получить ваш Telegram User ID"""
    print("🔍 Получение вашего Telegram User ID...")
    
    client = TelegramClient(
        settings.TELEGRAM_SESSION_NAME,
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH
    )
    
    try:
        await client.start(phone=settings.TELEGRAM_PHONE)
        
        # Получаем информацию о себе
        me = await client.get_me()
        user_id = me.id
        
        print(f"✅ Ваш Telegram User ID: {user_id}")
        print(f"👤 Имя: {me.first_name}")
        print(f"📱 Username: @{me.username}")
        
        print(f"\n📝 Добавьте эту строку в ваш .env файл:")
        print(f"TELEGRAM_USER_ID={user_id}")
        
        return user_id
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(get_user_id())
