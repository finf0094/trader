"""
Интегрированный запускатель автотрейдера с веб-интерфейсом
"""

import threading
import time
import logging
from auto_trader import AutoTrader
from web_interface import app

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class IntegratedTrader:
    """Интегрированный трейдер с веб-API"""

    def __init__(self):
        self.trader = AutoTrader()
        self.web_thread = None
        self.running = False

    def start_web_interface(self):
        """Запуск веб-интерфейса в отдельном потоке"""
        def run_flask():
            app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

        self.web_thread = threading.Thread(target=run_flask, daemon=True)
        self.web_thread.start()
        logging.info("🌐 Веб-интерфейс запущен на http://localhost:5000")

    def start(self):
        """Запуск всей системы"""
        print("🚀 Запуск интегрированной торговой системы...")
        print("=" * 60)

        # Запускаем веб-интерфейс
        self.start_web_interface()

        # Ждем немного, чтобы веб-сервер запустился
        time.sleep(2)

        print("✅ Система готова к работе!")
        print("📊 Веб-интерфейс: http://localhost:5000")
        print("🤖 Теперь можно запускать Telegram бота")
        print("=" * 60)
        print("Команды:")
        print("start  - Запустить торговлю")
        print("stop   - Остановить торговлю")
        print("status - Показать статус")
        print("web    - Открыть веб-интерфейс")
        print("quit   - Выйти")
        print("=" * 60)

        self.running = True

        # Основной цикл управления
        while self.running:
            try:
                command = input("\nВведите команду: ").strip().lower()

                if command == "start":
                    self.trader.start_trading()
                    print("✅ Торговля запущена!")

                elif command == "stop":
                    self.trader.stop_trading()
                    print("⏹️ Торговля остановлена!")

                elif command == "status":
                    status = self.trader.get_status()
                    print(f"\n📊 СТАТУС:")
                    print(f"Работает: {'✅ Да' if status['running'] else '❌ Нет'}")
                    print(f"Капитал: ${status['equity']:.2f}")
                    print(f"P&L: ${status['unrealized_pnl']:.2f}")
                    print(f"Позиций: {status['positions_count']}")

                elif command == "web":
                    print("🌐 Откройте браузер: http://localhost:5000")

                elif command == "quit":
                    print("🛑 Остановка системы...")
                    self.trader.stop_trading()
                    self.running = False
                    print("👋 До свидания!")
                    break

                else:
                    print("❌ Неизвестная команда")

            except KeyboardInterrupt:
                print("\n🛑 Остановка системы...")
                self.trader.stop_trading()
                self.running = False
                break

def main():
    """Главная функция"""
    integrated_trader = IntegratedTrader()
    integrated_trader.start()

if __name__ == "__main__":
    main()
