#!/usr/bin/env python3
"""
Простой скрипт для настройки аутентификации Telegram
"""
import asyncio
import os
import sys

# Добавляем путь к приложению
sys.path.append('/app')

async def main():
    print("🔐 Настройка аутентификации Telegram API...")
    
    # Импортируем после добавления пути
    try:
        from telethon import TelegramClient
        from app.core.config import settings
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("Установите telethon: pip install telethon")
        return
    
    print(f"📱 API ID: {settings.TELEGRAM_API_ID}")
    print(f"📞 Phone: {settings.TELEGRAM_PHONE}")
    
    # Создаем клиент
    client = TelegramClient(
        'telegram_bot_session',
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH
    )
    
    try:
        print("🚀 Запуск клиента...")
        await client.start(phone=settings.TELEGRAM_PHONE)
        
        print("✅ Аутентификация успешна!")
        
        # Получаем информацию о пользователе
        me = await client.get_me()
        print(f"👤 Пользователь: {me.first_name} (@{me.username})")
        
        # Проверяем доступ к каналу
        channel_id = settings.TELEGRAM_MONITORED_CHANNELS
        if channel_id:
            try:
                channel = await client.get_entity(int(channel_id))
                print(f"📺 Канал: {channel.title} (@{channel.username})")
                print(f"   ID: {channel.id}")
            except Exception as e:
                print(f"❌ Ошибка доступа к каналу: {e}")
                print("   Убедитесь, что вы подписаны на канал")
        
        print("\n🎉 Настройка завершена!")
        print("Теперь можно запускать парсинг каналов")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("\n🔧 Возможные решения:")
        print("1. Проверьте правильность API_ID и API_HASH")
        print("2. Убедитесь, что номер телефона правильный")
        print("3. Проверьте интернет-соединение")
    
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())



