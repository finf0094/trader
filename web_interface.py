"""
Веб-интерфейс с API для автоматического трейдера
"""

from flask import Flask, render_template, jsonify, request
import json
import threading
import time
from auto_trader import AutoTrader
import logging

app = Flask(__name__)
app.secret_key = 'trading_bot_secret_key'

# Глобальный экземпляр трейдера
trader = None

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_trader():
    """Инициализация трейдера"""
    global trader
    if trader is None:
        trader = AutoTrader()
        logger.info("Трейдер инициализирован")
    return trader


# Инициализируем трейдер при запуске модуля
init_trader()


@app.route('/')
def dashboard():
    """Главная страница дашборда"""
    return render_template('dashboard.html')


@app.route('/api/status')
def get_status():
    """API: Получение статуса трейдера"""
    try:
        trader = init_trader()
        status = trader.get_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Ошибка получения статуса: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/start', methods=['POST'])
def start_trading():
    """API: Запуск торговли"""
    try:
        trader = init_trader()
        trader.start_trading()
        return jsonify({"success": True, "message": "Торговля запущена"})
    except Exception as e:
        logger.error(f"Ошибка запуска торговли: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/stop', methods=['POST'])
def stop_trading():
    """API: Остановка торговли"""
    try:
        trader = init_trader()
        trader.stop_trading()
        return jsonify({"success": True, "message": "Торговля остановлена"})
    except Exception as e:
        logger.error(f"Ошибка остановки торговли: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_account():
    """API: Сброс счета"""
    try:
        trader = init_trader()
        trader.reset_account()
        return jsonify({"success": True, "message": "Счет сброшен"})
    except Exception as e:
        logger.error(f"Ошибка сброса счета: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/config')
def get_config():
    """API: Получение конфигурации"""
    try:
        trader = init_trader()
        return jsonify(trader.config)
    except Exception as e:
        logger.error(f"Ошибка получения конфигурации: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/config', methods=['POST'])
def save_config():
    """API: Сохранение конфигурации"""
    try:
        config = request.get_json()

        # Сохраняем в файл
        with open('trading_config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # Перезагружаем трейдер
        global trader
        trader = AutoTrader()

        return jsonify({"success": True, "message": "Конфигурация сохранена"})
    except Exception as e:
        logger.error(f"Ошибка сохранения конфигурации: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/statistics')
def get_statistics():
    """API: Получение статистики"""
    try:
        trader = init_trader()

        # Получаем статистику из базы данных
        import sqlite3
        conn = sqlite3.connect('trading_bot.db')
        cursor = conn.cursor()

        # Общая статистика
        cursor.execute('''
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(pnl) as total_pnl,
                MAX(pnl) as max_win,
                MIN(pnl) as max_loss
            FROM positions 
            WHERE status = 'CLOSED'
        ''')

        stats = cursor.fetchone()
        conn.close()

        if stats and stats[0] > 0:
            total_trades, winning_trades, total_pnl, max_win, max_loss = stats
            win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0

            statistics = {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "win_rate": win_rate,
                "total_pnl": total_pnl or 0,
                "max_win": max_win or 0,
                "max_loss": max_loss or 0
            }
        else:
            statistics = {
                "total_trades": 0,
                "winning_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "max_win": 0,
                "max_loss": 0
            }

        return jsonify({"statistics": statistics})
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/history')
def get_trade_history():
    """API: Получение истории сделок"""
    try:
        import sqlite3
        conn = sqlite3.connect('trading_bot.db')
        cursor = conn.cursor()

        cursor.execute('''
            SELECT symbol, quantity, entry_price, exit_price, entry_time, exit_time, pnl
            FROM positions 
            WHERE status = 'CLOSED'
            ORDER BY exit_time DESC
            LIMIT 50
        ''')

        trades = []
        for row in cursor.fetchall():
            symbol, quantity, entry_price, exit_price, entry_time, exit_time, pnl = row
            trades.append({
                "symbol": symbol,
                "quantity": quantity,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "pnl": pnl
            })

        conn.close()
        return jsonify({"trades": trades})
    except Exception as e:
        logger.error(f"Ошибка получения истории: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("🌐 Запуск веб-интерфейса...")
    print("📊 Дашборд: http://localhost:5000")
    print("🔌 API: http://localhost:5000/api/status")

    app.run(host='0.0.0.0', port=5000, debug=True)
