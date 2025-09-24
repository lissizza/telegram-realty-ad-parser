#!/usr/bin/env python3
"""
Скрипт для настройки аутентификации Telegram API
"""
import asyncio
import os
from telethon import TelegramClient
from app.core.config import settings

async def setup_telegram_auth():
    """Настройка аутентификации Telegram"""
    print("🔐 Настройка аутентификации Telegram API...")
    print(f"API ID: {settings.TELEGRAM_API_ID}")
    print(f"Phone: {settings.TELEGRAM_PHONE}")
    
    # Создаем клиент
    client = TelegramClient(
        settings.TELEGRAM_SESSION_NAME,
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH
    )
    
    try:
        print("📱 Запуск клиента...")
        await client.start(phone=settings.TELEGRAM_PHONE)
        
        print("✅ Аутентификация успешна!")
        print("📋 Информация о сессии:")
        
        # Получаем информацию о пользователе
        me = await client.get_me()
        print(f"   ID: {me.id}")
        print(f"   Имя: {me.first_name}")
        print(f"   Username: @{me.username}")
        
        # Проверяем доступ к каналу
        channel_id = settings.TELEGRAM_MONITORED_CHANNELS
        if channel_id:
            try:
                channel = await client.get_entity(int(channel_id))
                print(f"✅ Доступ к каналу: {channel.title}")
                print(f"   ID: {channel.id}")
                print(f"   Username: @{channel.username}")
            except Exception as e:
                print(f"❌ Ошибка доступа к каналу {channel_id}: {e}")
                print("   Убедитесь, что вы подписаны на канал")
        
        print("\n🎉 Аутентификация настроена!")
        print("Теперь можно запускать парсинг каналов")
        
    except Exception as e:
        print(f"❌ Ошибка аутентификации: {e}")
        print("\n🔧 Возможные решения:")
        print("1. Проверьте правильность API_ID и API_HASH")
        print("2. Убедитесь, что номер телефона правильный")
        print("3. Проверьте интернет-соединение")
        print("4. Убедитесь, что вы подписаны на канал")
    
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(setup_telegram_auth())



