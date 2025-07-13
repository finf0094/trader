import pandas as pd
import yfinance as yf
from backtesting import Backtest, Strategy
import numpy as np

class BalancedTradingStrategy(Strategy):
    """
    Сбалансированная торговая стратегия с разумными фильтрами
    """
    # Параметры индикаторов
    sma_fast = 10
    sma_slow = 25
    rsi_period = 14
    atr_period = 14

    # Параметры управления рисками
    stop_loss_pct = 0.08      # 8% стоп-лосс
    take_profit_pct = 0.15    # 15% тейк-профит
    max_drawdown_limit = 0.20 # 20% максимальная просадка
    position_size = 0.8       # 80% капитала в позиции

    # Более мягкие фильтры
    rsi_lower = 25            # RSI нижний уровень
    rsi_upper = 75            # RSI верхний уровень

    def init(self):
        """Инициализация индикаторов"""
        close = pd.Series(self.data.Close)
        high = pd.Series(self.data.High)
        low = pd.Series(self.data.Low)

        # Скользящие средние
        self.sma_fast_line = self.I(lambda: close.rolling(self.sma_fast).mean())
        self.sma_slow_line = self.I(lambda: close.rolling(self.sma_slow).mean())

        # RSI
        self.rsi = self.I(self._calculate_rsi, close, self.rsi_period)

        # Переменные для отслеживания
        self.entry_price = 0
        self.initial_equity = self.equity

    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Расчет RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        # Избегаем деления на ноль
        gain = gain.fillna(0)
        loss = loss.fillna(0)

        rs = gain / (loss + 1e-10)  # Добавляем малое число для избежания деления на ноль
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)  # Заполняем NaN средним значением RSI

    def _check_drawdown_limit(self) -> bool:
        """Проверка лимита просадки"""
        current_drawdown = (self.initial_equity - self.equity) / self.initial_equity
        return current_drawdown < self.max_drawdown_limit

    def _get_trend_direction(self) -> str:
        """Определение направления тренда"""
        if len(self.data) < self.sma_slow:
            return "neutral"

        fast_sma = self.sma_fast_line[-1]
        slow_sma = self.sma_slow_line[-1]
        price = self.data.Close[-1]

        if fast_sma > slow_sma and price > slow_sma:
            return "bullish"
        elif fast_sma < slow_sma and price < slow_sma:
            return "bearish"
        else:
            return "neutral"

    def next(self):
        """Основная логика торговли"""
        # Проверяем достаточно ли данных
        if len(self.data) < max(self.sma_slow, self.rsi_period):
            return

        # Проверяем лимит просадки
        if not self._check_drawdown_limit():
            if self.position:
                self.position.close()
            return

        # Текущие значения
        price = self.data.Close[-1]
        fast_sma = self.sma_fast_line[-1]
        slow_sma = self.sma_slow_line[-1]
        rsi_val = self.rsi[-1]

        # Определяем тренд
        trend = self._get_trend_direction()

        # ЛОГИКА ВХОДА В ПОЗИЦИЮ
        if not self.position:
            # Сигнал на покупку
            bullish_cross = (fast_sma > slow_sma and
                           self.sma_fast_line[-2] <= self.sma_slow_line[-2])

            # Альтернативный сигнал: цена выше обеих SMA
            price_momentum = (price > fast_sma and
                            price > slow_sma and
                            self.data.Close[-1] > self.data.Close[-2])

            # RSI фильтр - не покупаем в перекупленности
            rsi_ok = rsi_val < self.rsi_upper

            # Основной сигнал покупки
            buy_signal = ((bullish_cross or price_momentum) and
                         rsi_ok and
                         trend in ["bullish", "neutral"])

            if buy_signal:
                self.buy(size=self.position_size)
                self.entry_price = price

        # ЛОГИКА ВЫХОДА ИЗ ПОЗИЦИИ
        elif self.position:
            # Стоп-лосс
            stop_loss_price = self.entry_price * (1 - self.stop_loss_pct)

            # Тейк-профит
            take_profit_price = self.entry_price * (1 + self.take_profit_pct)

            # Технический сигнал на продажу
            bearish_cross = (fast_sma < slow_sma and
                           self.sma_fast_line[-2] >= self.sma_slow_line[-2])

            # RSI в зоне перекупленности
            rsi_exit = rsi_val > self.rsi_upper

            # Цена ниже медленной SMA (потеря тренда)
            trend_break = price < slow_sma

            # Условия выхода
            exit_conditions = [
                price <= stop_loss_price,    # Стоп-лосс
                price >= take_profit_price,  # Тейк-профит
                bearish_cross,               # Технический сигнал
                (rsi_exit and trend_break)   # RSI + потеря тренда
            ]

            if any(exit_conditions):
                self.position.close()
                self.entry_price = 0

def run_enhanced_backtest(ticker: str, start_date: str = '2020-01-01', end_date: str = '2024-01-01'):
    """Запуск улучшенного бэктеста с детальной аналитикой"""
    try:
        # Загружаем данные
        print(f"Загрузка данных для {ticker}...")
        df = yf.download(ticker, start=start_date, end=end_date, interval='1d')

        if df.empty or len(df) < 100:
            return None

        # Обработка данных
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.dropna(inplace=True)
        df.reset_index(inplace=True)

        # Разделение данных
        split_point = int(len(df) * 0.7)
        df_train = df[:split_point].copy()
        df_test = df[split_point:].copy()

        print(f"  Период обучения: {len(df_train)} дней")
        print(f"  Период тестирования: {len(df_test)} дней")

        # Бэктестирование
        bt_train = Backtest(df_train, BalancedTradingStrategy, cash=10000, commission=0.001)
        stats_train = bt_train.run()

        bt_test = Backtest(df_test, BalancedTradingStrategy, cash=10000, commission=0.001)
        stats_test = bt_test.run()

        # Расчет дополнительных метрик
        def safe_get(stats, key, default=0):
            try:
                return stats[key] if not pd.isna(stats[key]) else default
            except:
                return default

        result = {
            'ticker': ticker,
            'train_return': safe_get(stats_train, 'Return [%]'),
            'test_return': safe_get(stats_test, 'Return [%]'),
            'train_sharpe': safe_get(stats_train, 'Sharpe Ratio'),
            'test_sharpe': safe_get(stats_test, 'Sharpe Ratio'),
            'train_max_dd': safe_get(stats_train, 'Max. Drawdown [%]'),
            'test_max_dd': safe_get(stats_test, 'Max. Drawdown [%]'),
            'train_trades': len(stats_train['_trades']),
            'test_trades': len(stats_test['_trades']),
            'train_win_rate': safe_get(stats_train, 'Win Rate [%]'),
            'test_win_rate': safe_get(stats_test, 'Win Rate [%]'),
            'buy_hold_return': ((df['Close'].iloc[-1] / df['Close'].iloc[0]) - 1) * 100
        }

        return result

    except Exception as e:
        print(f"  Ошибка для {ticker}: {e}")
        return None

def analyze_strategy_performance(results):
    """Детальный анализ производительности стратегии"""
    if not results:
        print("❌ Нет результатов для анализа")
        return

    df = pd.DataFrame(results)

    print("\n" + "=" * 120)
    print("ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print("=" * 120)

    for _, row in df.iterrows():
        print(f"\n📊 {row['ticker']}:")
        print(f"   Обучение:    Return: {row['train_return']:6.1f}% | MaxDD: {row['train_max_dd']:6.1f}% | Trades: {row['train_trades']:2d} | WinRate: {row['train_win_rate']:5.1f}%")
        print(f"   Тест:        Return: {row['test_return']:6.1f}% | MaxDD: {row['test_max_dd']:6.1f}% | Trades: {row['test_trades']:2d} | WinRate: {row['test_win_rate']:5.1f}%")
        print(f"   Buy & Hold:  Return: {row['buy_hold_return']:6.1f}%")

        # Оценка качества
        consistency = abs(row['train_return'] - row['test_return'])
        outperforms_bh = row['test_return'] > row['buy_hold_return']
        good_drawdown = row['test_max_dd'] > -25
        enough_trades = row['test_trades'] >= 2

        score = sum([
            consistency < 30,      # Консистентность
            outperforms_bh,        # Превосходит Buy & Hold
            good_drawdown,         # Приемлемая просадка
            enough_trades,         # Достаточно сделок
            row['test_return'] > 0 # Положительная доходность
        ])

        print(f"   Оценка качества: {score}/5 {'✅' if score >= 3 else '❌'}")

    # Общая статистика
    print("\n" + "=" * 120)
    print("СВОДНАЯ СТАТИСТИКА:")
    print("=" * 120)

    avg_test_return = df['test_return'].mean()
    avg_train_return = df['train_return'].mean()
    avg_consistency = abs(df['train_return'] - df['test_return']).mean()
    outperformed_bh = (df['test_return'] > df['buy_hold_return']).sum()
    positive_returns = (df['test_return'] > 0).sum()

    print(f"📈 Средняя доходность на тесте: {avg_test_return:.1f}%")
    print(f"📊 Средняя консистентность: {avg_consistency:.1f}%")
    print(f"🏆 Превзошли Buy & Hold: {outperformed_bh}/{len(df)} активов")
    print(f"✅ Положительная доходность: {positive_returns}/{len(df)} активов")

    # Рекомендации
    print("\n" + "=" * 120)
    print("ИТОГОВЫЕ РЕКОМЕНДАЦИИ:")
    print("=" * 120)

    good_performers = df[(df['test_return'] > 0) &
                        (df['test_max_dd'] > -25) &
                        (df['test_trades'] >= 2)]['ticker'].tolist()

    if good_performers:
        print(f"✅ Рекомендованные активы: {', '.join(good_performers)}")
        print("\n📋 Следующие шаги для реальной торговли:")
        print("   1. Форвард-тест на демо-счете 3-6 месяцев")
        print("   2. Начать с минимальными суммами (100-500$)")
        print("   3. Строго следовать стоп-лоссам")
        print("   4. Ведите торговый дневник")
        print("   5. Не рискуйте более 2% капитала на сделку")
    else:
        print("❌ Стратегия требует дальнейшей доработки")
        print("\n📋 Необходимые улучшения:")
        print("   1. Оптимизация параметров")
        print("   2. Добавление новых фильтров")
        print("   3. Тестирование на других таймфреймах")
        print("   4. Использование других индикаторов")

if __name__ == "__main__":
    # Тестируем стратегию на разных активах
    tickers = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'META', 'GOOGL', 'AMZN', 'SPY']

    print("🚀 ТЕСТИРОВАНИЕ СБАЛАНСИРОВАННОЙ ТОРГОВОЙ СТРАТЕГИИ")
    print("=" * 120)

    results = []
    for ticker in tickers:
        result = run_enhanced_backtest(ticker)
        if result:
            results.append(result)

    analyze_strategy_performance(results)
