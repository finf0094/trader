import pandas as pd
import yfinance as yf
from backtesting import Backtest, Strategy
import numpy as np

class ImprovedSmaStrategy(Strategy):
    # Параметры стратегии
    sma_short = 10
    sma_long = 20
    stop_loss = 0.05  # 5% стоп-лосс
    take_profit = 0.10  # 10% тейк-профит
    risk_per_trade = 0.02  # 2% риска на сделку

    def init(self):
        # Короткая и длинная SMA
        close = pd.Series(self.data.Close)
        self.sma_s = self.I(lambda: close.rolling(self.sma_short).mean(), overlay=True)
        self.sma_l = self.I(lambda: close.rolling(self.sma_long).mean(), overlay=True)

        # ATR для волатильности
        high = pd.Series(self.data.High)
        low = pd.Series(self.data.Low)
        close_prev = close.shift(1)

        tr1 = high - low
        tr2 = abs(high - close_prev)
        tr3 = abs(low - close_prev)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        self.atr = self.I(lambda: tr.rolling(14).mean())

    def next(self):
        # Проверяем достаточно ли данных
        if len(self.data) < max(self.sma_short, self.sma_long):
            return

        # Текущие значения
        price = self.data.Close[-1]
        sma_s_val = self.sma_s[-1]
        sma_l_val = self.sma_l[-1]

        # Сигнал на покупку: короткая SMA пересекает длинную снизу вверх
        if (sma_s_val > sma_l_val and
            self.sma_s[-2] <= self.sma_l[-2] and  # Пересечение произошло
            not self.position):

            # Покупаем фиксированную долю капитала (например, 90%)
            self.buy(size=0.9)

        # Сигнал на продажу: короткая SMA пересекает длинную сверху вниз
        elif (sma_s_val < sma_l_val and
              self.sma_s[-2] >= self.sma_l[-2] and  # Пересечение произошло
              self.position):
            self.position.close()

        # Управление рисками для открытых позиций
        elif self.position:
            entry_price = self.position.entry_price if hasattr(self.position, 'entry_price') else None
            if entry_price is None:
                return

            current_price = price

            # Стоп-лосс
            if current_price <= entry_price * (1 - self.stop_loss):
                self.position.close()

            # Тейк-профит
            elif current_price >= entry_price * (1 + self.take_profit):
                self.position.close()

# Функция для более надежного тестирования
def robust_backtest(ticker, strategy_class, start_date='2020-01-01', end_date='2024-01-01'):
    """
    Более надежный бэктест с разделением на in-sample и out-of-sample
    """
    # Загружаем больше данных
    df = yf.download(ticker, start=start_date, end=end_date, interval='1d')

    if df.empty:
        return None

    # Убираем MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df.dropna(inplace=True)
    df.reset_index(inplace=True)

    # Разделяем данные: 70% для обучения, 30% для тестирования
    split_point = int(len(df) * 0.7)
    df_train = df[:split_point].copy()
    df_test = df[split_point:].copy()

    # Тестируем на обучающей выборке
    bt_train = Backtest(df_train, strategy_class, cash=10000, commission=0.001)
    stats_train = bt_train.run()

    # Тестируем на тестовой выборке (out-of-sample)
    bt_test = Backtest(df_test, strategy_class, cash=10000, commission=0.001)
    stats_test = bt_test.run()

    return {
        'ticker': ticker,
        'train_return': stats_train['Return [%]'],
        'test_return': stats_test['Return [%]'],
        'train_sharpe': stats_train['Sharpe Ratio'],
        'test_sharpe': stats_test['Sharpe Ratio'],
        'train_max_dd': stats_train['Max. Drawdown [%]'],
        'test_max_dd': stats_test['Max. Drawdown [%]'],
        'train_trades': len(stats_train['_trades']),
        'test_trades': len(stats_test['_trades'])
    }

if __name__ == "__main__":
    tickers = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'META']
    results = []

    print("Тестирование улучшенной стратегии...")
    print("=" * 80)

    for ticker in tickers:
        print(f"\nТестирование {ticker}...")
        result = robust_backtest(ticker, ImprovedSmaStrategy)
        if result:
            results.append(result)
            print(f"  Обучение: Return={result['train_return']:.1f}%, Sharpe={result['train_sharpe']:.2f}, MaxDD={result['train_max_dd']:.1f}%")
            print(f"  Тест:     Return={result['test_return']:.1f}%, Sharpe={result['test_sharpe']:.2f}, MaxDD={result['test_max_dd']:.1f}%")

    # Анализ результатов
    df_results = pd.DataFrame(results)
    print("\n" + "=" * 80)
    print("СВОДКА РЕЗУЛЬТАТОВ:")
    print("=" * 80)
    print(df_results.to_string(index=False, float_format='%.2f'))

    # Проверка на переоптимизацию
    print("\n" + "=" * 80)
    print("АНАЛИЗ ПЕРЕОПТИМИЗАЦИИ:")
    print("=" * 80)
    for _, row in df_results.iterrows():
        diff = row['train_return'] - row['test_return']
        status = "ПЕРЕОПТИМИЗАЦИЯ" if diff > 20 else "НОРМА"
        print(f"{row['ticker']}: Разница {diff:.1f}% - {status}")
