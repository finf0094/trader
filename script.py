import pandas as pd
import yfinance as yf
from backtesting import Backtest, Strategy
from backtesting.lib import SignalStrategy, crossover
import numpy as np

# Задаём параметры
tickers = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'META']
sma_windows = [5, 10, 20, 30, 50]
intervals = ['1d', '1h', '15m']  # '1d' — день, '1h' — час, '15m' — 15 минут
periods = {'1d': '2y', '1h': '60d', '15m': '7d'}  # Нужно достаточно данных для длинных SMA!

results = []

# Функция для расчета SMA
def calculate_sma(data, window):
    return data.rolling(window=window, min_periods=1).mean()

# Класс стратегии для backtesting.py
class SmaCross(Strategy):
    n1 = 10  # SMA период

    def init(self):
        # Предварительно рассчитываем SMA до инициализации стратегии
        close_prices = pd.Series(self.data.Close)
        sma_values = calculate_sma(close_prices, self.n1)
        self.sma = self.I(lambda: sma_values, overlay=True)

    def next(self):
        if len(self.data) < self.n1:
            return

        if self.data.Close[-1] > self.sma[-1]:
            if not self.position:
                self.buy()
        else:
            if self.position:
                self.position.close()

for ticker in tickers:
    for interval in intervals:
        print(f"\n=== {ticker} {interval} ===")
        period = periods[interval]
        # Скачиваем данные
        df = yf.download(ticker, period=period, interval=interval)
        if df.empty or len(df) < max(sma_windows) + 10:
            print("  Нет данных или мало данных для анализа")
            continue

        # Убираем MultiIndex если он есть
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        # Преобразуем в формат для backtesting.py
        df_bt = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df_bt.dropna(inplace=True)
        df_bt.reset_index(inplace=True)

        # Проверяем название колонки с датой
        if 'Date' not in df_bt.columns:
            if 'Datetime' in df_bt.columns:
                df_bt.rename(columns={'Datetime': 'Date'}, inplace=True)
            elif df_bt.index.name == 'Date' or df_bt.index.name == 'Datetime':
                df_bt.reset_index(inplace=True)
                df_bt.rename(columns={df_bt.columns[0]: 'Date'}, inplace=True)

        # Тестируем все варианты SMA
        for sma in sma_windows:
            # Наследуем стратегию с нужным SMA
            class CustomSma(SmaCross):
                n1 = sma

            try:
                bt = Backtest(df_bt, CustomSma, cash=10_000, commission=.001, exclusive_orders=True)
                stats = bt.run()
                results.append({
                    'Ticker': ticker,
                    'Interval': interval,
                    'SMA': sma,
                    'Trades': stats['_trades'].shape[0],
                    'WinRate': round(stats['Win Rate [%]'], 2),
                    'AvgWin': round(stats['Avg. Trade [%]'], 2),
                    'EV': round(stats['Expectancy [%]'], 2),
                    'Equity Final': round(stats['Equity Final [$]'], 2),
                    'Return [%]': round(stats['Return [%]'], 2)
                })
                print(
                    f"  SMA{sma} | Trades: {stats['_trades'].shape[0]} | WinRate: {round(stats['Win Rate [%]'], 2)} | EV: {round(stats['Expectancy [%]'], 2)}% | Return: {round(stats['Return [%]'], 2)}%")
            except Exception as e:
                print(f"  Ошибка для SMA{sma}: {e}")

# Финальная таблица
df_results = pd.DataFrame(results)
print("\n--- Лучшие результаты по каждому тикеру/интервалу ---")
if not df_results.empty:
    best_for_each = df_results.sort_values(['Ticker', 'Interval', 'EV'], ascending=[True, True, False]).groupby(
        ['Ticker', 'Interval']).first().reset_index()
    print(best_for_each.to_string(index=False))
    # df_results.to_csv("backtesting_sma_results.csv", index=False)
else:
    print("Нет результатов ни по одному тикеру.")
