import pandas as pd
import yfinance as yf
import numpy as np
import time
import sqlite3
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
import threading
import json
from dataclasses import dataclass
from enum import Enum
import asyncio
import aiohttp
import requests

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)


class OrderType(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    current_price: float = 0
    unrealized_pnl: float = 0


@dataclass
class Order:
    symbol: str
    order_type: OrderType
    quantity: float
    price: float
    timestamp: datetime
    status: OrderStatus = OrderStatus.PENDING
    order_id: str = ""


class TradingDatabase:
    """Класс для работы с базой данных торговых операций"""

    def __init__(self, db_name: str = "trading_bot.db"):
        self.db_name = db_name
        self.init_database()

    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Таблица позиций
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS positions
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           symbol
                           TEXT
                           NOT
                           NULL,
                           quantity
                           REAL
                           NOT
                           NULL,
                           entry_price
                           REAL
                           NOT
                           NULL,
                           entry_time
                           TEXT
                           NOT
                           NULL,
                           exit_price
                           REAL,
                           exit_time
                           TEXT,
                           stop_loss
                           REAL,
                           take_profit
                           REAL,
                           pnl
                           REAL,
                           status
                           TEXT
                           DEFAULT
                           'OPEN'
                       )
                       ''')

        # Таблица ордеров
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS orders
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           symbol
                           TEXT
                           NOT
                           NULL,
                           order_type
                           TEXT
                           NOT
                           NULL,
                           quantity
                           REAL
                           NOT
                           NULL,
                           price
                           REAL
                           NOT
                           NULL,
                           timestamp
                           TEXT
                           NOT
                           NULL,
                           status
                           TEXT
                           NOT
                           NULL,
                           order_id
                           TEXT
                       )
                       ''')

        # Таблица для хранения настроек
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS settings
                       (
                           key
                           TEXT
                           PRIMARY
                           KEY,
                           value
                           TEXT
                           NOT
                           NULL
                       )
                       ''')

        # Таблица для статистики
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS statistics
                       (
                           date
                           TEXT
                           PRIMARY
                           KEY,
                           total_equity
                           REAL,
                           daily_pnl
                           REAL,
                           trades_count
                           INTEGER,
                           win_rate
                           REAL
                       )
                       ''')

        conn.commit()
        conn.close()

    def save_position(self, position: Position):
        """Сохранение позиции в базу данных"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
                       INSERT INTO positions (symbol, quantity, entry_price, entry_time, stop_loss, take_profit)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ''', (position.symbol, position.quantity, position.entry_price,
                             position.entry_time.isoformat(), position.stop_loss, position.take_profit))

        conn.commit()
        conn.close()

    def update_position_exit(self, symbol: str, exit_price: float, pnl: float):
        """Обновление позиции при закрытии"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
                       UPDATE positions
                       SET exit_price = ?,
                           exit_time  = ?,
                           pnl        = ?,
                           status     = 'CLOSED'
                       WHERE symbol = ?
                         AND status = 'OPEN'
                       ''', (exit_price, datetime.now().isoformat(), pnl, symbol))

        conn.commit()
        conn.close()

    def save_order(self, order: Order):
        """Сохранение ордера в базу данных"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
                       INSERT INTO orders (symbol, order_type, quantity, price, timestamp, status, order_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ''', (order.symbol, order.order_type.value, order.quantity, order.price,
                             order.timestamp.isoformat(), order.status.value, order.order_id))

        conn.commit()
        conn.close()


class MarketDataProvider:
    """Провайдер рыночных данных"""

    def __init__(self):
        self.cache = {}
        self.cache_timeout = 60  # секунд

    def get_current_price(self, symbol: str) -> float:
        """Получение текущей цены актива"""
        try:
            # Проверяем кэш
            now = datetime.now()
            if symbol in self.cache:
                cached_data, timestamp = self.cache[symbol]
                if (now - timestamp).seconds < self.cache_timeout:
                    return cached_data

            # Получаем новые данные
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval="1m")

            if not data.empty:
                current_price = data['Close'].iloc[-1]
                self.cache[symbol] = (current_price, now)
                return current_price
            else:
                logging.warning(f"Нет данных для {symbol}")
                return 0

        except Exception as e:
            logging.error(f"Ошибка получения цены для {symbol}: {e}")
            return 0

    def get_historical_data(self, symbol: str, period: str = "1d", interval: str = "1m") -> pd.DataFrame:
        """Получение исторических данных"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)
            return data
        except Exception as e:
            logging.error(f"Ошибка получения исторических данных для {symbol}: {e}")
            return pd.DataFrame()


class TradingStrategy:
    """Торговая стратегия на основе SMA и RSI"""

    def __init__(self, config: Dict):
        self.sma_fast = config.get('sma_fast', 10)
        self.sma_slow = config.get('sma_slow', 25)
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_lower = config.get('rsi_lower', 25)
        self.rsi_upper = config.get('rsi_upper', 75)
        self.stop_loss_pct = config.get('stop_loss_pct', 0.08)
        self.take_profit_pct = config.get('take_profit_pct', 0.15)

    def calculate_indicators(self, data: pd.DataFrame) -> Dict:
        """Расчет технических индикаторов"""
        if len(data) < max(self.sma_slow, self.rsi_period):
            return {}

        close = data['Close']

        # SMA
        sma_fast = close.rolling(window=self.sma_fast).mean()
        sma_slow = close.rolling(window=self.sma_slow).mean()

        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))

        return {
            'close': close.iloc[-1],
            'sma_fast': sma_fast.iloc[-1],
            'sma_slow': sma_slow.iloc[-1],
            'sma_fast_prev': sma_fast.iloc[-2] if len(sma_fast) > 1 else sma_fast.iloc[-1],
            'sma_slow_prev': sma_slow.iloc[-2] if len(sma_slow) > 1 else sma_slow.iloc[-1],
            'rsi': rsi.iloc[-1]
        }

    def generate_signal(self, symbol: str, data: pd.DataFrame, has_position: bool) -> str:
        """Генерация торгового сигнала"""
        indicators = self.calculate_indicators(data)

        if not indicators:
            return "HOLD"

        close = indicators['close']
        sma_fast = indicators['sma_fast']
        sma_slow = indicators['sma_slow']
        sma_fast_prev = indicators['sma_fast_prev']
        sma_slow_prev = indicators['sma_slow_prev']
        rsi = indicators['rsi']

        # Сигнал на покупку
        if not has_position:
            # Пересечение SMA
            bullish_cross = (sma_fast > sma_slow and sma_fast_prev <= sma_slow_prev)

            # Альтернативный сигнал
            price_momentum = (close > sma_fast and close > sma_slow and
                              data['Close'].iloc[-1] > data['Close'].iloc[-2])

            # RSI фильтр
            rsi_ok = rsi < self.rsi_upper

            if (bullish_cross or price_momentum) and rsi_ok:
                return "BUY"

        # Сигнал на продажу
        elif has_position:
            # Пересечение SMA
            bearish_cross = (sma_fast < sma_slow and sma_fast_prev >= sma_slow_prev)

            # RSI сигнал
            rsi_exit = rsi > self.rsi_upper

            # Потеря тренда
            trend_break = close < sma_slow

            if bearish_cross or (rsi_exit and trend_break):
                return "SELL"

        return "HOLD"


class RiskManager:
    """Менеджер рисков"""

    def __init__(self, config: Dict):
        self.max_position_size = config.get('max_position_size', 0.2)  # Уменьшено с 0.8 до 0.2
        self.max_risk_per_trade = config.get('max_risk_per_trade', 0.01)  # Уменьшено с 0.02 до 0.01
        self.max_drawdown = config.get('max_drawdown', 0.20)
        self.max_daily_loss = config.get('max_daily_loss', 0.05)
        self.max_positions = config.get('max_positions', 3)  # Максимум 3 позиции одновременно

    def calculate_position_size(self, equity: float, entry_price: float, stop_loss: float) -> float:
        """Расчет размера позиции"""
        # Проверяем валидность данных
        if entry_price <= 0 or stop_loss <= 0 or equity <= 0:
            logging.warning(
                f"РИСК: Некорректные данные для расчета позиции: equity={equity}, entry_price={entry_price}, stop_loss={stop_loss}")
            return 0

        if stop_loss >= entry_price:
            logging.warning(f"РИСК: Стоп-лосс ({stop_loss:.2f}) больше или равен цене входа ({entry_price:.2f})")
            return 0

        # Максимальная сумма риска на сделку
        risk_amount = equity * self.max_risk_per_trade

        # Расстояние до стоп-лосса в процентах
        stop_distance_pct = (entry_price - stop_loss) / entry_price

        # Размер позиции на основе риска
        risk_based_quantity = risk_amount / (entry_price * stop_distance_pct)

        # Максимальный размер позиции на основе капитала
        max_position_value = equity * self.max_position_size
        max_quantity = max_position_value / entry_price

        # Берем минимальное значение
        final_quantity = min(risk_based_quantity, max_quantity)

        # Дополнительная проверка - не больше 5% от капитала на одну позицию
        conservative_limit = (equity * 0.05) / entry_price
        final_quantity = min(final_quantity, conservative_limit)

        logging.info(f"РИСК: Расчет позиции для {entry_price:.2f}: risk_based={risk_based_quantity:.2f}, "
                     f"max_quantity={max_quantity:.2f}, conservative={conservative_limit:.2f}, "
                     f"final={final_quantity:.2f}")

        return max(0, final_quantity)

    def can_open_position(self, current_positions_count: int) -> bool:
        """Проверка, можно ли открыть новую позицию"""
        return current_positions_count < self.max_positions

    def check_risk_limits(self, equity: float, initial_equity: float, daily_pnl: float) -> bool:
        """Проверка лимитов риска"""
        # Проверка максимальной просадки
        drawdown = (initial_equity - equity) / initial_equity
        if drawdown > self.max_drawdown:
            logging.warning(f"РИСК: Достигнут лимит просадки: {drawdown:.2%}")
            return False

        # Проверка дневного лимита потерь
        if daily_pnl < 0 and abs(daily_pnl) / equity > self.max_daily_loss:
            logging.warning(f"РИСК: Достигнут дневной лимит потерь: {daily_pnl:.2f}")
            return False

        return True


class AutoTrader:
    """Главный класс автоматического трейдера"""

    def __init__(self, config_file: str = "trading_config.json"):
        self.load_config(config_file)
        self.db = TradingDatabase()
        self.market_data = MarketDataProvider()
        self.strategy = TradingStrategy(self.config['strategy'])
        self.risk_manager = RiskManager(self.config['risk'])
        self.telegram = TelegramNotifier()  # Добавляем Telegram уведомления

        self.positions: Dict[str, Position] = {}
        self.equity = self.config['account']['initial_equity']
        self.initial_equity = self.equity
        self.is_running = False
        self.trading_thread = None

        logging.info("Автотрейдер инициализирован")

    def load_config(self, config_file: str):
        """Загрузка конфигурации"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            # Создаем конфигурацию по умолчанию
            self.config = {
                "account": {
                    "initial_equity": 10000,
                    "demo_mode": True
                },
                "strategy": {
                    "sma_fast": 10,
                    "sma_slow": 25,
                    "rsi_period": 14,
                    "rsi_lower": 25,
                    "rsi_upper": 75,
                    "stop_loss_pct": 0.05,  # Уменьшено с 0.08 до 0.05
                    "take_profit_pct": 0.10  # Уменьшено с 0.15 до 0.10
                },
                "risk": {
                    "max_position_size": 0.10,  # Уменьшено с 0.8 до 0.10 (10% капитала на позицию)
                    "max_risk_per_trade": 0.005,  # Уменьшено с 0.02 до 0.005 (0.5% риска на сделку)
                    "max_drawdown": 0.15,  # Уменьшено с 0.20 до 0.15
                    "max_daily_loss": 0.03,  # Уменьшено с 0.05 до 0.03
                    "max_positions": 2  # Уменьшено с 3 до 2
                },
                "symbols": ["AAPL", "MSFT"],  # Уменьшено количество символов для тестирования
                "trading": {
                    "check_interval": 60,
                    "market_hours": {
                        "start": "09:30",
                        "end": "16:00"
                    },
                    "test_mode": True  # Добавлен тестовый режим
                }
            }

            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)

            logging.info(f"Создан файл конфигурации: {config_file}")

    def is_market_open(self) -> bool:
        """Проверка, открыт ли рынок"""
        # Если включен тестовый режим - работаем всегда
        if self.config['trading'].get('test_mode', False):
            return True

        now = datetime.now()

        # Проверяем день недели (понедельник=0, воскресенье=6)
        if now.weekday() >= 5 and not self.config['trading'].get('ignore_weekends', False):
            return False

        # Проверяем время торгов
        market_start = datetime.strptime(self.config['trading']['market_hours']['start'], "%H:%M").time()
        market_end = datetime.strptime(self.config['trading']['market_hours']['end'], "%H:%M").time()

        current_time = now.time()
        return market_start <= current_time <= market_end

    def place_order(self, symbol: str, order_type: OrderType, quantity: float, price: float) -> bool:
        """Размещение ордера (имитация для демо-режима)"""
        if self.config['account']['demo_mode']:
            # Демо-режим: имитируем исполнение ордера
            order = Order(
                symbol=symbol,
                order_type=order_type,
                quantity=quantity,
                price=price,
                timestamp=datetime.now(),
                status=OrderStatus.FILLED,
                order_id=f"DEMO_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

            self.db.save_order(order)
            logging.info(f"Демо-ордер исполнен: {order_type.value} {quantity:.2f} {symbol} по цене {price:.2f}")
            return True
        else:
            # Здесь должна быть интеграция с реальным брокером
            # Например, Interactive Brokers, Alpaca, или другой API
            logging.warning("Реальная торговля не реализована. Используйте demo_mode=true")
            return False

    def open_position(self, symbol: str, current_price: float):
        """Открытие позиции"""
        # Проверяем, можно ли открыть новую позицию
        if not self.risk_manager.can_open_position(len(self.positions)):
            logging.warning(f"РИСК: Достигнут максимум открытых позиций ({len(self.positions)})")
            return

        stop_loss = current_price * (1 - self.strategy.stop_loss_pct)
        take_profit = current_price * (1 + self.strategy.take_profit_pct)

        quantity = self.risk_manager.calculate_position_size(self.equity, current_price, stop_loss)

        if quantity <= 0:
            logging.warning(f"РИСК: Расчетное количество акций = {quantity:.4f}, позиция не открывается")
            return

        # Проверяем, достаточно ли капитала
        position_cost = quantity * current_price
        if position_cost > self.equity * 0.95:  # Оставляем 5% буфер
            logging.warning(f"РИСК: Недостаточно капитала для позиции. Требуется: ${position_cost:.2f}, Доступно: ${self.equity:.2f}")
            return

        position = Position(
            symbol=symbol,
            quantity=quantity,
            entry_price=current_price,
            entry_time=datetime.now(),
            stop_loss=stop_loss,
            take_profit=take_profit,
            current_price=current_price
        )

        if self.place_order(symbol, OrderType.BUY, quantity, current_price):
            self.positions[symbol] = position
            self.db.save_position(position)
            self.equity -= quantity * current_price

            logging.info(f"Открыта позиция: {symbol} - {quantity:.4f} акций по ${current_price:.2f}")
            logging.info(f"Стоп-лосс: ${stop_loss:.2f}, Тейк-профит: ${take_profit:.2f}")
            logging.info(f"Потрачено: ${position_cost:.2f}, Осталось капитала: ${self.equity:.2f}")

            # Отправляем уведомление в Telegram
            self.telegram.send_trade_notification("BUY", symbol, quantity, current_price)
        else:
            logging.error(f"ОШИБКА: Не удалось разместить ордер для {symbol}")

    def close_position(self, symbol: str, current_price: float):
        """Закрытие позиции"""
        if symbol in self.positions:
            position = self.positions[symbol]

            if self.place_order(symbol, OrderType.SELL, position.quantity, current_price):
                pnl = (current_price - position.entry_price) * position.quantity
                self.equity += position.quantity * current_price

                self.db.update_position_exit(symbol, current_price, pnl)

                logging.info(f"Закрыта позиция: {symbol} - P&L: {pnl:.2f}")

                # Отправляем уведомление в Telegram о продаже
                self.telegram.send_trade_notification("SELL", symbol, position.quantity, current_price, pnl)

                del self.positions[symbol]

    def update_positions(self):
        """Обновление открытых позиций"""
        for symbol, position in list(self.positions.items()):
            current_price = self.market_data.get_current_price(symbol)

            if current_price > 0:
                position.current_price = current_price
                position.unrealized_pnl = (current_price - position.entry_price) * position.quantity

                # Проверка стоп-лосса и тейк-профита
                if (current_price <= position.stop_loss or
                        current_price >= position.take_profit):
                    self.close_position(symbol, current_price)

    def trading_loop(self):
        """Основной торговый цикл"""
        logging.info("ЗАПУСК: Торговый цикл запущен!")

        while self.is_running:
            try:
                current_time = datetime.now()
                market_open = self.is_market_open()

                logging.info(
                    f"ВРЕМЯ: {current_time.strftime('%H:%M:%S')}, Рынок: {'ОТКРЫТ' if market_open else 'ЗАКРЫТ'}")

                if not market_open:
                    logging.info("ОЖИДАНИЕ: Рынок закрыт. Ожидание...")
                    time.sleep(300)  # Проверяем каждые 5 минут
                    continue

                logging.info("АНАЛИЗ: Начинаю анализ рынка...")

                # Обновляем открытые позиции
                self.update_positions()

                # Проверяем риски
                daily_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
                if not self.risk_manager.check_risk_limits(self.equity, self.initial_equity, daily_pnl):
                    logging.warning("РИСК: Достигнуты лимиты риска. Торговля приостановлена.")
                    # НЕ вызываем stop_trading() из того же потока
                    self.is_running = False
                    break

                # Анализируем сигналы для каждого символа
                for symbol in self.config['symbols']:
                    try:
                        logging.info(f"ПРОВЕРКА: Анализирую {symbol}...")

                        data = self.market_data.get_historical_data(symbol, period="1d", interval="5m")

                        if data.empty:
                            logging.warning(f"ОШИБКА: Нет данных для {symbol}")
                            continue

                        logging.info(f"ДАННЫЕ: {symbol}: получено {len(data)} записей данных")

                        if len(data) >= 50:  # Достаточно данных для анализа
                            has_position = symbol in self.positions
                            signal = self.strategy.generate_signal(symbol, data, has_position)
                            current_price = self.market_data.get_current_price(symbol)

                            logging.info(
                                f"СИГНАЛ: {symbol}: Цена={current_price:.2f}, Сигнал={signal}, Позиция={'Есть' if has_position else 'Нет'}")

                            if signal == "BUY" and not has_position and current_price > 0:
                                logging.info(f"ПОКУПКА: Покупаю {symbol}")
                                self.open_position(symbol, current_price)
                            elif signal == "SELL" and has_position:
                                logging.info(f"ПРОДАЖА: Продаю {symbol}")
                                self.close_position(symbol, current_price)
                        else:
                            logging.warning(f"ДАННЫЕ: {symbol}: недостаточно данных ({len(data)} записей)")

                    except Exception as e:
                        logging.error(f"ОШИБКА: Ошибка анализа {symbol}: {e}")

                # Логирование статуса
                total_unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
                logging.info(
                    f"СТАТУС: Капитал: ${self.equity:.2f}, Нереализованная P&L: ${total_unrealized:.2f}, Позиций: {len(self.positions)}")

                # Ожидание до следующей проверки
                interval = self.config['trading']['check_interval']
                logging.info(f"ОЖИДАНИЕ: {interval} секунд до следующей проверки...")
                time.sleep(interval)

            except Exception as e:
                logging.error(f"КРИТИЧЕСКАЯ ОШИБКА в торговом цикле: {e}")
                time.sleep(60)

    def start_trading(self):
        """Запуск автоматической торговли"""
        if self.is_running:
            logging.warning("Торговля уже запущена")
            return

        self.is_running = True
        self.trading_thread = threading.Thread(target=self.trading_loop)
        self.trading_thread.daemon = True
        self.trading_thread.start()

        logging.info("Автоматическая торговля запущена")

    def stop_trading(self):
        """Остановка автоматической торговли"""
        self.is_running = False
        if self.trading_thread:
            self.trading_thread.join()

        logging.info("Автоматическая торговля остановлена")

    def reset_account(self):
        """Сброс счета к начальным значениям"""
        self.equity = self.config['account']['initial_equity']
        self.initial_equity = self.equity
        self.positions.clear()
        logging.info(f"СБРОС: Счет сброшен к начальному капиталу ${self.equity:.2f}")

    def get_status(self) -> Dict:
        """Получение текущего статуса"""
        total_unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())

        return {
            "running": self.is_running,
            "equity": self.equity,
            "unrealized_pnl": total_unrealized,
            "total_equity": self.equity + total_unrealized,
            "positions_count": len(self.positions),
            "positions": [
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "entry_price": pos.entry_price,
                    "current_price": pos.current_price,
                    "unrealized_pnl": pos.unrealized_pnl
                }
                for pos in self.positions.values()
            ]
        }


class TelegramNotifier:
    """Класс для отправки уведомлений в Telegram"""

    def __init__(self):
        self.bot_token = None
        self.chat_id = None
        self.enabled = False
        self.load_telegram_config()

    def load_telegram_config(self):
        """Загрузка конфигурации Telegram"""
        try:
            with open('telegram_config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)

            self.bot_token = config.get('bot_token')
            self.chat_id = config.get('chat_id')

            if (self.bot_token and self.bot_token != "YOUR_BOT_TOKEN_HERE" and
                self.chat_id and self.chat_id != "YOUR_CHAT_ID_HERE"):
                self.enabled = True
                logging.info("Telegram уведомления включены")
            else:
                logging.warning("Telegram уведомления отключены - не заполнена конфигурация")

        except FileNotFoundError:
            logging.warning("Файл telegram_config.json не найден - Telegram уведомления отключены")
        except Exception as e:
            logging.error(f"Ошибка загрузки Telegram конфигурации: {e}")

    def send_notification(self, message: str):
        """Отправка уведомления в Telegram"""
        if not self.enabled:
            return

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }

            response = requests.post(url, data=data, timeout=5)
            if response.status_code == 200:
                logging.info("Telegram уведомление отправлено")
            else:
                logging.error(f"Ошибка отправки в Telegram: {response.status_code}")

        except Exception as e:
            logging.error(f"Ошибка отправки Telegram уведомления: {e}")

    def send_trade_notification(self, trade_type: str, symbol: str, quantity: float, price: float, pnl: float = None):
        """Отправка уведомления о сделке"""
        if not self.enabled:
            return

        if trade_type.upper() == "BUY":
            emoji = "💰"
            action = "Покупка"
            message = (
                f"{emoji} <b>{action} акций</b>\n\n"
                f"📊 <b>Символ:</b> {symbol}\n"
                f"💎 <b>Количество:</b> {quantity:.2f}\n"
                f"💰 <b>Цена:</b> ${price:.2f}\n"
                f"💵 <b>Сумма:</b> ${quantity * price:.2f}\n"
                f"🕒 <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}"
            )
        elif trade_type.upper() == "SELL":
            emoji = "💸"
            action = "Продажа"
            pnl_emoji = "📈" if pnl and pnl >= 0 else "📉"
            pnl_sign = "+" if pnl and pnl >= 0 else ""

            message = (
                f"{emoji} <b>{action} акций</b>\n\n"
                f"📊 <b>Символ:</b> {symbol}\n"
                f"💎 <b>Количество:</b> {quantity:.2f}\n"
                f"💰 <b>Цена:</b> ${price:.2f}\n"
                f"💵 <b>Сумма:</b> ${quantity * price:.2f}\n"
                f"{pnl_emoji} <b>Прибыль:</b> {pnl_sign}${pnl:.2f if pnl else 0:.2f}\n"
                f"🕒 <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}"
            )
        else:
            return

        self.send_notification(message)

    def send_risk_warning(self, warning_type: str, details: str):
        """Отправка предупреждения о рисках"""
        if not self.enabled:
            return

        message = (
            f"⚠️ <b>ПРЕДУПРЕЖДЕНИЕ О РИСКАХ</b>\n\n"
            f"🚨 <b>Тип:</b> {warning_type}\n"
            f"📝 <b>Детали:</b> {details}\n"
            f"🕒 <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}"
        )

        self.send_notification(message)


def main():
    """Главная функция для запуска автотрейдера"""
    trader = AutoTrader()

    try:
        print("🤖 АВТОМАТИЧЕСКИЙ ТРЕЙДЕР")
        print("=" * 50)
        print("Команды:")
        print("start  - Запустить торговлю")
        print("stop   - Остановить торговлю")
        print("status - Показать статус")
        print("quit   - Выйти")
        print("=" * 50)

        while True:
            command = input("\nВведите команду: ").strip().lower()

            if command == "start":
                trader.start_trading()

            elif command == "stop":
                trader.stop_trading()

            elif command == "status":
                status = trader.get_status()
                print(f"\n📊 СТАТУС ТРЕЙДЕРА:")
                print(f"Работает: {'✅ Да' if status['running'] else '❌ Нет'}")
                print(f"Equity: ${status['equity']:.2f}")
                print(f"Unrealized P&L: ${status['unrealized_pnl']:.2f}")
                print(f"Total Equity: ${status['total_equity']:.2f}")
                print(f"Открытых позиций: {status['positions_count']}")

                if status['positions']:
                    print("\n📈 ОТКРЫТЫЕ ПОЗИЦИИ:")
                    for pos in status['positions']:
                        print(f"  {pos['symbol']}: {pos['quantity']:.2f} @ ${pos['entry_price']:.2f} "
                              f"(Current: ${pos['current_price']:.2f}, P&L: ${pos['unrealized_pnl']:.2f})")

            elif command == "quit":
                trader.stop_trading()
                print("👋 До свидания!")
                break

            else:
                print("❌ Неизвестная команда")

    except KeyboardInterrupt:
        trader.stop_trading()
        print("\n👋 Торговля остановлена пользователем")


if __name__ == "__main__":
    main()
