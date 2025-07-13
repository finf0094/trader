"""
Тестовый скрипт для проверки работы API и Telegram бота
"""

import requests
import json
import time

def test_api():
    """Тестирование API трейдера"""
    base_url = "http://localhost:5000"

    print("🧪 Тестирование API автотрейдера...")
    print("=" * 50)

    # Тест 1: Проверка статуса
    try:
        response = requests.get(f"{base_url}/api/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ API статуса работает")
            print(f"   Капитал: ${data.get('equity', 0):.2f}")
            print(f"   Работает: {'Да' if data.get('running') else 'Нет'}")
        else:
            print(f"❌ API статуса не работает: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка подключения к API: {e}")
        return False

    # Тест 2: Попытка запуска торговли
    try:
        response = requests.post(f"{base_url}/api/start", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ API запуска торговли работает")
            else:
                print(f"⚠️ API ответил с ошибкой: {data.get('error')}")
        else:
            print(f"❌ API запуска не работает: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")

    # Тест 3: Остановка торговли
    try:
        response = requests.post(f"{base_url}/api/stop", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ API остановки торговли работает")
            else:
                print(f"⚠️ API ответил с ошибкой: {data.get('error')}")
    except Exception as e:
        print(f"❌ Ошибка остановки: {e}")

    print("=" * 50)
    return True

def check_telegram_config():
    """Проверка конфигурации Telegram"""
    print("\n🤖 Проверка конфигурации Telegram...")

    try:
        with open('telegram_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        bot_token = config.get('bot_token')
        chat_id = config.get('chat_id')

        if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
            print("❌ Bot token не настроен")
            print("📝 Настройте bot_token в telegram_config.json")
            return False

        if not chat_id or chat_id == "YOUR_CHAT_ID_HERE":
            print("❌ Chat ID не настроен")
            print("📝 Настройте chat_id в telegram_config.json")
            return False

        print("✅ Конфигурация Telegram выглядит корректно")
        return True

    except FileNotFoundError:
        print("❌ Файл telegram_config.json не найден")
        return False
    except Exception as e:
        print(f"❌ Ошибка чтения конфигурации: {e}")
        return False

def main():
    """Главная функция тестирования"""
    print("🔧 ДИАГНОСТИКА ТОРГОВОЙ СИСТЕМЫ")
    print("=" * 60)

    # Проверяем API
    api_ok = test_api()

    # Проверяем Telegram
    telegram_ok = check_telegram_config()

    print("\n📋 РЕЗУЛЬТАТЫ ДИАГНОСТИКИ:")
    print("=" * 30)
    print(f"API трейдера: {'✅ OK' if api_ok else '❌ FAIL'}")
    print(f"Telegram конфиг: {'✅ OK' if telegram_ok else '❌ FAIL'}")

    if api_ok and telegram_ok:
        print("\n🎉 Система готова к работе!")
        print("📋 Инструкция:")
        print("1. Запустите: python integrated_trader.py")
        print("2. В другом терминале: python telegram_bot.py")
        print("3. Отправьте /start вашему Telegram боту")
    else:
        print("\n⚠️ Требуется настройка:")
        if not api_ok:
            print("- Запустите веб-интерфейс (python integrated_trader.py)")
        if not telegram_ok:
            print("- Настройте telegram_config.json с вашими данными")

if __name__ == "__main__":
    main()
