#!/usr/bin/env python3
"""
Скрипт для автоматического обновления ngrok URL в .env файле
"""
import requests
import os
import re

def get_ngrok_url():
    """Получить текущий ngrok URL"""
    try:
        response = requests.get("http://localhost:4040/api/tunnels")
        if response.status_code == 200:
            data = response.json()
            for tunnel in data.get("tunnels", []):
                if tunnel.get("proto") == "https":
                    return tunnel.get("public_url")
    except Exception as e:
        print(f"Ошибка получения ngrok URL: {e}")
    return None

def update_env_file(new_url):
    """Обновить .env файл с новым URL"""
    env_file = ".env"
    if not os.path.exists(env_file):
        print("Файл .env не найден")
        return False
    
    # Читаем файл
    with open(env_file, 'r') as f:
        content = f.read()
    
    # Обновляем API_BASE_URL
    pattern = r'API_BASE_URL=.*'
    replacement = f'API_BASE_URL={new_url}'
    new_content = re.sub(pattern, replacement, content)
    
    # Записываем обратно
    with open(env_file, 'w') as f:
        f.write(new_content)
    
    print(f"✅ Обновлен API_BASE_URL: {new_url}")
    return True

def main():
    """Основная функция"""
    print("🔍 Получение текущего ngrok URL...")
    
    ngrok_url = get_ngrok_url()
    if not ngrok_url:
        print("❌ Не удалось получить ngrok URL")
        print("Убедитесь, что ngrok запущен на localhost:4040")
        return
    
    print(f"📡 Найден ngrok URL: {ngrok_url}")
    
    if update_env_file(ngrok_url):
        print("🔄 Перезапуск приложения...")
        os.system("docker-compose restart app")
        print("✅ Готово!")
    else:
        print("❌ Ошибка обновления .env файла")

if __name__ == "__main__":
    main()



