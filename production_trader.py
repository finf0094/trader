"""
Продакшн версия интегрированного трейдера для сервера
"""

import threading
import time
import logging
import sys
import os
from auto_trader import AutoTrader
from web_interface import app

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)

class ProductionTrader:
    """Продакшн версия интегрированного трейдера"""

    def __init__(self):
        self.trader = AutoTrader()
        self.web_thread = None
        self.running = False

    def start_web_interface(self):
        """Запуск веб-интерфейса в продакшн режиме"""
        def run_flask():
            # Отключаем debug режим и reloader для продакшна
            app.run(
                host='0.0.0.0',
                port=5000,
                debug=False,
                use_reloader=False,
                threaded=True
            )

        self.web_thread = threading.Thread(target=run_flask, daemon=True)
        self.web_thread.start()
        logging.info("🌐 Веб-интерфейс запущен на http://0.0.0.0:5000")

    def start(self):
        """Запуск системы в продакшн режиме"""
        logging.info("🚀 Запуск торговой системы в продакшн режиме...")

        # Запускаем веб-интерфейс
        self.start_web_interface()

        # Ждем немного, чтобы веб-сервер запустился
        time.sleep(2)

        logging.info("✅ Система готова к работе!")
        logging.info("📊 Веб-интерфейс доступен на порту 5000")
        logging.info("🤖 Telegram бот может подключаться к API")

        self.running = True

        # Бесконечный цикл для поддержания работы сервиса
        try:
            while self.running:
                time.sleep(60)  # Проверяем каждую минуту

                # Проверяем, что веб-поток еще жив
                if self.web_thread and not self.web_thread.is_alive():
                    logging.error("❌ Веб-интерфейс остановился, перезапускаем...")
                    self.start_web_interface()

        except KeyboardInterrupt:
            logging.info("🛑 Получен сигнал остановки")
            self.stop()
        except Exception as e:
            logging.error(f"❌ Критическая ошибка: {e}")
            self.stop()

    def stop(self):
        """Остановка системы"""
        logging.info("🛑 Остановка торговой системы...")
        self.running = False
        if hasattr(self.trader, 'stop_trading'):
            self.trader.stop_trading()

def main():
    """Главная функция для продакшн запуска"""

    # Проверяем, что мы находимся в правильной директории
    if not os.path.exists('auto_trader.py'):
        logging.error("❌ Файл auto_trader.py не найден в текущей директории")
        sys.exit(1)

    if not os.path.exists('web_interface.py'):
        logging.error("❌ Файл web_interface.py не найден в текущей директории")
        sys.exit(1)

    # Создаем и запускаем продакшн трейдер
    production_trader = ProductionTrader()

    try:
        production_trader.start()
    except Exception as e:
        logging.error(f"❌ Ошибка запуска: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
