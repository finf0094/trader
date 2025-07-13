import pandas as pd
import yfinance as yf
from backtesting import Backtest, Strategy
import numpy as np
from typing import Dict, List, Tuple

class AdvancedTradingStrategy(Strategy):
    """
    Продвинутая торговая стратегия с множественными фильтрами
    """
    # Параметры индикаторов
    sma_fast = 10
    sma_slow = 30
    rsi_period = 14
    atr_period = 14
    volume_ma_period = 20

    # Параметры управления рисками
    max_risk_per_trade = 0.02  # 2% риска на сделку
    stop_loss_atr_mult = 2.0   # Стоп-лосс = 2 * ATR
    take_profit_atr_mult = 3.0 # Тейк-профит = 3 * ATR
    max_drawdown_limit = 0.15  # Максимальная просадка 15%
    max_positions = 1          # Максимум позиций одновременно

    # Фильтры для входа
    min_volume_ratio = 1.2     # Минимум 120% от средней громкости
    rsi_oversold = 35          # RSI для перепроданности
    rsi_overbought = 65        # RSI для перекупленности
    trend_strength_min = 0.02  # Минимальная сила тренда

    def init(self):
        """Инициализация индикаторов"""
        close = pd.Series(self.data.Close)
        high = pd.Series(self.data.High)
        low = pd.Series(self.data.Low)
        volume = pd.Series(self.data.Volume)

        # Скользящие средние
        self.sma_fast_line = self.I(lambda: close.rolling(self.sma_fast).mean())
        self.sma_slow_line = self.I(lambda: close.rolling(self.sma_slow).mean())

        # RSI
        self.rsi = self.I(self._calculate_rsi, close, self.rsi_period)

        # ATR для волатильности
        self.atr = self.I(self._calculate_atr, high, low, close, self.atr_period)

        # Средняя громкость
        self.volume_ma = self.I(lambda: volume.rolling(self.volume_ma_period).mean())

        # Переменные для отслеживания
        self.entry_price = 0
        self.initial_equity = self.equity

    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Расчет RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """Расчет Average True Range"""
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def _check_trend_strength(self) -> float:
        """Проверка силы тренда"""
        if len(self.data) < self.sma_slow:
            return 0

        # Расчет наклона SMA
        sma_current = self.sma_slow_line[-1]
        sma_prev = self.sma_slow_line[-5] if len(self.data) >= 5 else self.sma_slow_line[-1]

        if sma_prev == 0:
            return 0

        trend_strength = (sma_current - sma_prev) / sma_prev
        return trend_strength

    def _check_volume_confirmation(self) -> bool:
        """Проверка подтверждения объемом"""
        if len(self.data) < self.volume_ma_period:
            return False

        current_volume = self.data.Volume[-1]
        avg_volume = self.volume_ma[-1]

        return current_volume > (avg_volume * self.min_volume_ratio)

    def _calculate_position_size(self) -> float:
        """Расчет размера позиции на основе ATR и риска"""
        if len(self.data) < self.atr_period:
            return 0

        current_price = self.data.Close[-1]
        atr_value = self.atr[-1]

        if atr_value == 0:
            return 0

        # Стоп-лосс на основе ATR
        stop_distance = atr_value * self.stop_loss_atr_mult

        # Размер позиции на основе риска
        risk_amount = self.equity * self.max_risk_per_trade
        position_value = risk_amount / (stop_distance / current_price)

        # Ограничиваем максимальным размером позиции
        max_position_value = self.equity * 0.8
        position_value = min(position_value, max_position_value)

        return position_value / current_price / self.equity  # Возвращаем долю от капитала

    def _check_drawdown_limit(self) -> bool:
        """Проверка лимита просадки"""
        current_drawdown = (self.initial_equity - self.equity) / self.initial_equity
        return current_drawdown < self.max_drawdown_limit

    def next(self):
        """Основная логика торговли"""
        # Проверяем достаточно ли данных
        if len(self.data) < max(self.sma_slow, self.rsi_period, self.atr_period):
            return

        # Проверяем лимит просадки
        if not self._check_drawdown_limit():
            if self.position:
                self.position.close()
            return

        # Текущие значения
        price = self.data.Close[-1]
        sma_fast_val = self.sma_fast_line[-1]
        sma_slow_val = self.sma_slow_line[-1]
        rsi_val = self.rsi[-1]
        atr_val = self.atr[-1]

        # Проверяем силу тренда
        trend_strength = self._check_trend_strength()

        # СИГНАЛЫ НА ПОКУПКУ
        if not self.position:
            # Основной сигнал: пересечение SMA + фильтры
            bullish_cross = (sma_fast_val > sma_slow_val and
                           self.sma_fast_line[-2] <= self.sma_slow_line[-2])

            # Фильтры для покупки
            rsi_filter = self.rsi_oversold <= rsi_val <= 70  # RSI не в экстремуме
            volume_filter = self._check_volume_confirmation()
            trend_filter = trend_strength > self.trend_strength_min
            price_above_slow_sma = price > sma_slow_val

            # Дополнительный фильтр: цена не слишком далеко от SMA
            price_distance = abs(price - sma_slow_val) / sma_slow_val
            distance_filter = price_distance < 0.05  # Не более 5% от SMA

            if (bullish_cross and rsi_filter and volume_filter and
                trend_filter and price_above_slow_sma and distance_filter):

                position_size = self._calculate_position_size()
                if position_size > 0.01:  # Минимальный размер позиции
                    self.buy(size=position_size)
                    self.entry_price = price

        # УПРАВЛЕНИЕ ОТКРЫТОЙ ПОЗИЦИЕЙ
        elif self.position:
            # Стоп-лосс на основе ATR
            stop_loss_price = self.entry_price - (atr_val * self.stop_loss_atr_mult)

            # Тейк-профит на основе ATR
            take_profit_price = self.entry_price + (atr_val * self.take_profit_atr_mult)

            # Трейлинг стоп
            trailing_stop = price - (atr_val * self.stop_loss_atr_mult)

            # Сигнал на закрытие по техническим условиям
            bearish_cross = (sma_fast_val < sma_slow_val and
                           self.sma_fast_line[-2] >= self.sma_slow_line[-2])

            # RSI в зоне перекупленности
            rsi_exit = rsi_val > self.rsi_overbought

            # Условия выхода
            if (price <= stop_loss_price or           # Стоп-лосс
                price >= take_profit_price or         # Тейк-профит
                bearish_cross or                      # Технический сигнал
                rsi_exit):                           # RSI сигнал
                self.position.close()
                self.entry_price = 0

class PortfolioBacktest:
    """Класс для тестирования портфеля стратегий"""

    def __init__(self, tickers: List[str], start_date: str = '2020-01-01', end_date: str = '2024-01-01'):
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date

    def run_single_backtest(self, ticker: str) -> Dict:
        """Запуск бэктеста для одного актива"""
        try:
            # Загружаем данные
            df = yf.download(ticker, start=self.start_date, end=self.end_date, interval='1d')

            if df.empty or len(df) < 100:
                return None

            # Убираем MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)

            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            df.dropna(inplace=True)
            df.reset_index(inplace=True)

            # Разделяем на обучение (70%) и тест (30%)
            split_point = int(len(df) * 0.7)
            df_train = df[:split_point].copy()
            df_test = df[split_point:].copy()

            # Тестирование на обучающей выборке
            bt_train = Backtest(df_train, AdvancedTradingStrategy, cash=10000, commission=0.001)
            stats_train = bt_train.run()

            # Тестирование на тестовой выборке
            bt_test = Backtest(df_test, AdvancedTradingStrategy, cash=10000, commission=0.001)
            stats_test = bt_test.run()

            return {
                'ticker': ticker,
                'train_return': stats_train['Return [%]'],
                'test_return': stats_test['Return [%]'],
                'train_sharpe': stats_train.get('Sharpe Ratio', 0),
                'test_sharpe': stats_test.get('Sharpe Ratio', 0),
                'train_max_dd': stats_train['Max. Drawdown [%]'],
                'test_max_dd': stats_test['Max. Drawdown [%]'],
                'train_trades': len(stats_train['_trades']),
                'test_trades': len(stats_test['_trades']),
                'train_win_rate': stats_train.get('Win Rate [%]', 0),
                'test_win_rate': stats_test.get('Win Rate [%]', 0),
                'consistency': abs(stats_train['Return [%]'] - stats_test['Return [%]'])
            }

        except Exception as e:
            print(f"Ошибка для {ticker}: {e}")
            return None

    def run_portfolio_test(self) -> pd.DataFrame:
        """Запуск тестирования портфеля"""
        results = []

        print("Тестирование продвинутой стратегии...")
        print("=" * 100)

        for ticker in self.tickers:
            print(f"\nТестирование {ticker}...")
            result = self.run_single_backtest(ticker)

            if result:
                results.append(result)
                print(f"  Обучение: Return={result['train_return']:.1f}%, "
                      f"Sharpe={result['train_sharpe']:.2f}, "
                      f"MaxDD={result['train_max_dd']:.1f}%, "
                      f"WinRate={result['train_win_rate']:.1f}%")
                print(f"  Тест:     Return={result['test_return']:.1f}%, "
                      f"Sharpe={result['test_sharpe']:.2f}, "
                      f"MaxDD={result['test_max_dd']:.1f}%, "
                      f"WinRate={result['test_win_rate']:.1f}%")
                print(f"  Консистентность: {result['consistency']:.1f}% разница")

        return pd.DataFrame(results)

    def analyze_results(self, df_results: pd.DataFrame):
        """Анализ результатов"""
        if df_results.empty:
            print("Нет результатов для анализа")
            return

        print("\n" + "=" * 100)
        print("ДЕТАЛЬНЫЙ АНАЛИЗ РЕЗУЛЬТАТОВ:")
        print("=" * 100)
        print(df_results.round(2).to_string(index=False))

        print("\n" + "=" * 100)
        print("АНАЛИЗ НАДЕЖНОСТИ СТРАТЕГИИ:")
        print("=" * 100)

        consistent_strategies = []

        for _, row in df_results.iterrows():
            consistency_score = 100 - row['consistency']

            # Критерии качества стратегии
            criteria = {
                'Положительная доходность на тесте': row['test_return'] > 0,
                'Низкая просадка на тесте': row['test_max_dd'] > -20,
                'Достаточно сделок': row['test_trades'] >= 3,
                'Хорошая консистентность': row['consistency'] < 30,
                'Приемлемый Sharpe': row['test_sharpe'] > 0.5 if not pd.isna(row['test_sharpe']) else False
            }

            passed_criteria = sum(criteria.values())
            total_criteria = len(criteria)

            print(f"\n{row['ticker']}:")
            print(f"  Критериев пройдено: {passed_criteria}/{total_criteria}")
            print(f"  Консистентность: {consistency_score:.1f}%")

            if passed_criteria >= 3:
                consistent_strategies.append(row['ticker'])
                status = "✅ РЕКОМЕНДУЕТСЯ для дальнейшего тестирования"
            else:
                status = "❌ НЕ РЕКОМЕНДУЕТСЯ"

            print(f"  Статус: {status}")

        print("\n" + "=" * 100)
        print("ИТОГОВЫЕ РЕКОМЕНДАЦИИ:")
        print("=" * 100)

        if consistent_strategies:
            print(f"✅ Перспективные активы: {', '.join(consistent_strategies)}")
            print("📋 Следующие шаги:")
            print("   1. Форвард-тестирование на демо-счете 3-6 месяцев")
            print("   2. Оптимизация параметров для каждого актива")
            print("   3. Тест в разных рыночных условиях")
            print("   4. Начать с минимальными позициями на реальном счете")
        else:
            print("❌ Ни один актив не прошел все критерии качества")
            print("📋 Требуется:")
            print("   1. Дальнейшая разработка стратегии")
            print("   2. Добавление новых фильтров")
            print("   3. Тестирование на других активах")
            print("   4. Изменение параметров стратегии")

if __name__ == "__main__":
    # Тестируем на различных активах
    tickers = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'META', 'GOOGL', 'AMZN', 'SPY']

    portfolio = PortfolioBacktest(tickers)
    results_df = portfolio.run_portfolio_test()
    portfolio.analyze_results(results_df)
