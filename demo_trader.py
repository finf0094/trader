import pandas as pd
import yfinance as yf
import time
from datetime import datetime
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('demo_trader.log'),
        logging.StreamHandler()
    ]
)

class DemoTrader:
    """Простой демо-трейдер для немедленного тестирования"""

    def __init__(self):
        self.symbols = ['AAPL', 'MSFT', 'NVDA', 'META', 'GOOGL']
        self.equity = 10000
        self.positions = {}
        self.running = False

    def get_current_price(self, symbol):
        """Получение текущей цены"""
        try:
            logging.info(f"🔍 Загружаю данные для {symbol}...")
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval="5m")

            if not data.empty:
                price = data['Close'].iloc[-1]
                logging.info(f"💰 {symbol}: текущая цена ${price:.2f}")
                return price
            else:
                logging.warning(f"❌ Нет данных для {symbol}")
                return 0
        except Exception as e:
            logging.error(f"❌ Ошибка получения цены {symbol}: {e}")
            return 0

    def analyze_symbol(self, symbol):
        """Анализ символа и генерация сигнала"""
        try:
            logging.info(f"📊 Анализирую {symbol}...")

            # Получаем исторические данные
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="5d", interval="15m")

            if len(data) < 50:
                logging.warning(f"⚠️ {symbol}: недостаточно данных ({len(data)} записей)")
                return "HOLD", 0

            logging.info(f"📈 {symbol}: получено {len(data)} записей данных")

            # Простая логика: SMA 10 и 20
            close = data['Close']
            sma_10 = close.rolling(10).mean()
            sma_20 = close.rolling(20).mean()

            current_price = close.iloc[-1]
            sma10_current = sma_10.iloc[-1]
            sma20_current = sma_20.iloc[-1]
            sma10_prev = sma_10.iloc[-2]
            sma20_prev = sma_20.iloc[-2]

            logging.info(f"📊 {symbol}: SMA10={sma10_current:.2f}, SMA20={sma20_current:.2f}")

            # Сигнал на покупку: SMA10 пересекает SMA20 снизу вверх
            if sma10_current > sma20_current and sma10_prev <= sma20_prev:
                logging.info(f"🟢 {symbol}: СИГНАЛ ПОКУПКИ! (SMA пересечение)")
                return "BUY", current_price

            # Сигнал на продажу: SMA10 пересекает SMA20 сверху вниз
            elif sma10_current < sma20_current and sma10_prev >= sma20_prev:
                logging.info(f"🔴 {symbol}: СИГНАЛ ПРОДАЖИ! (SMA пересечение)")
                return "SELL", current_price

            # Дополнительные сигналы для демо
            elif current_price > sma10_current and current_price > sma20_current:
                # Цена выше обеих SMA - потенциальная покупка
                if len([s for s in self.positions if self.positions[s] > 0]) == 0:  # Нет позиций
                    logging.info(f"🟡 {symbol}: СЛАБЫЙ СИГНАЛ ПОКУПКИ (цена выше SMA)")
                    return "BUY", current_price

            logging.info(f"⚪ {symbol}: УДЕРЖАНИЕ (нет сильных сигналов)")
            return "HOLD", current_price

        except Exception as e:
            logging.error(f"❌ Ошибка анализа {symbol}: {e}")
            return "HOLD", 0

    def execute_trade(self, symbol, signal, price):
        """Исполнение сделки"""
        if signal == "BUY" and symbol not in self.positions:
            # Покупаем на $2000
            quantity = 2000 / price
            self.positions[symbol] = quantity
            self.equity -= 2000

            logging.info(f"✅ ПОКУПКА ИСПОЛНЕНА: {symbol}")
            logging.info(f"   Количество: {quantity:.2f} акций")
            logging.info(f"   Цена: ${price:.2f}")
            logging.info(f"   Сумма: $2000.00")
            logging.info(f"   Остаток капитала: ${self.equity:.2f}")

        elif signal == "SELL" and symbol in self.positions:
            # Продаем
            quantity = self.positions[symbol]
            value = quantity * price
            profit = value - 2000

            del self.positions[symbol]
            self.equity += value

            logging.info(f"✅ ПРОДАЖА ИСПОЛНЕНА: {symbol}")
            logging.info(f"   Количество: {quantity:.2f} акций")
            logging.info(f"   Цена: ${price:.2f}")
            logging.info(f"   Сумма: ${value:.2f}")
            logging.info(f"   Прибыль: ${profit:.2f}")
            logging.info(f"   Капитал: ${self.equity:.2f}")

    def run_demo(self, cycles=5):
        """Запуск демо-режима"""
        logging.info("🚀 ЗАПУСК ДЕМО-ТРЕЙДЕРА")
        logging.info("=" * 50)
        logging.info(f"Начальный капитал: ${self.equity:.2f}")
        logging.info(f"Анализируемые активы: {', '.join(self.symbols)}")
        logging.info("=" * 50)

        for cycle in range(cycles):
            logging.info(f"\n🔄 ЦИКЛ {cycle + 1}/{cycles}")
            logging.info(f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}")

            for symbol in self.symbols:
                signal, price = self.analyze_symbol(symbol)

                if signal in ["BUY", "SELL"] and price > 0:
                    self.execute_trade(symbol, signal, price)

                time.sleep(2)  # Небольшая пауза между анализами

            # Статус портфеля
            total_value = self.equity
            for symbol, quantity in self.positions.items():
                current_price = self.get_current_price(symbol)
                if current_price > 0:
                    total_value += quantity * current_price

            logging.info(f"\n💼 СТАТУС ПОРТФЕЛЯ:")
            logging.info(f"   Денежные средства: ${self.equity:.2f}")
            logging.info(f"   Открытых позиций: {len(self.positions)}")
            for symbol, quantity in self.positions.items():
                current_price = self.get_current_price(symbol)
                value = quantity * current_price if current_price > 0 else 0
                logging.info(f"   {symbol}: {quantity:.2f} акций (${value:.2f})")
            logging.info(f"   ОБЩАЯ СТОИМОСТЬ: ${total_value:.2f}")
            logging.info(f"   ПРИБЫЛЬ/УБЫТОК: ${total_value - 10000:.2f}")

            if cycle < cycles - 1:
                logging.info(f"\n⏳ Ожидание 30 секунд до следующего цикла...")
                time.sleep(30)

        logging.info("\n🏁 ДЕМО ЗАВЕРШЕНО!")

if __name__ == "__main__":
    demo = DemoTrader()
    demo.run_demo(cycles=3)  # 3 цикла анализа
