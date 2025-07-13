"""
Telegram бот для мониторинга автоматического трейдера
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingTelegramBot:
    """Telegram бот для уведомлений о торговле"""

    def __init__(self, bot_token: str, chat_id: str, trader_api_url: str = "http://localhost:5000"):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.trader_api_url = trader_api_url

        self.bot = Bot(token=bot_token)
        self.dp = Dispatcher()

        # Регистрируем обработчики
        self._register_handlers()

        # Флаги для отслеживания состояния
        self.notifications_enabled = True
        self.last_positions = {}

    def _register_handlers(self):
        """Регистрация обработчиков команд"""

        @self.dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            """Команда /start"""
            keyboard = self._get_main_keyboard()

            await message.answer(
                "🤖 <b>Добро пожаловать в Торгового Бота!</b>\n\n"
                "Я буду уведомлять вас о всех торговых операциях:\n"
                "💰 Покупка и продажа акций\n"
                "📊 Текущий статус портфеля\n"
                "⚠️ Предупреждения о рисках\n\n"
                "Выберите действие:",
                parse_mode="HTML",
                reply_markup=keyboard
            )

        @self.dp.message(Command("status"))
        async def cmd_status(message: types.Message):
            """Команда /status"""
            await self._send_status(message.chat.id)

        @self.dp.message(Command("positions"))
        async def cmd_positions(message: types.Message):
            """Команда /positions"""
            await self._send_positions(message.chat.id)

        @self.dp.message(Command("stats"))
        async def cmd_stats(message: types.Message):
            """Команда /stats"""
            await self._send_statistics(message.chat.id)

        @self.dp.message(Command("settings"))
        async def cmd_settings(message: types.Message):
            """Команда /settings"""
            await self._send_settings(message.chat.id)

        @self.dp.callback_query()
        async def process_callback(callback: CallbackQuery):
            """Обработка callback запросов"""
            await self._handle_callback(callback)

    def _get_main_keyboard(self) -> InlineKeyboardMarkup:
        """Главная клавиатура"""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📊 Статус", callback_data="status"),
            InlineKeyboardButton(text="💼 Позиции", callback_data="positions")
        )
        builder.row(
            InlineKeyboardButton(text="📈 Статистика", callback_data="stats"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")
        )
        builder.row(
            InlineKeyboardButton(text="▶️ Запустить", callback_data="start_trading"),
            InlineKeyboardButton(text="⏹️ Остановить", callback_data="stop_trading")
        )
        return builder.as_markup()

    def _get_settings_keyboard(self) -> InlineKeyboardMarkup:
        """Клавиатура настроек"""
        builder = InlineKeyboardBuilder()

        notify_text = "🔕 Выкл. уведомления" if self.notifications_enabled else "🔔 Вкл. уведомления"
        builder.row(
            InlineKeyboardButton(text=notify_text, callback_data="toggle_notifications")
        )
        builder.row(
            InlineKeyboardButton(text="🔄 Сбросить счет", callback_data="reset_account")
        )
        builder.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
        )
        return builder.as_markup()

    async def _handle_callback(self, callback: CallbackQuery):
        """Обработка callback запросов"""
        data = callback.data

        if data == "status":
            await self._send_status(callback.message.chat.id, callback.message.message_id)
        elif data == "positions":
            await self._send_positions(callback.message.chat.id, callback.message.message_id)
        elif data == "stats":
            await self._send_statistics(callback.message.chat.id, callback.message.message_id)
        elif data == "settings":
            await self._send_settings(callback.message.chat.id, callback.message.message_id)
        elif data == "start_trading":
            await self._start_trading(callback.message.chat.id, callback.message.message_id)
        elif data == "stop_trading":
            await self._stop_trading(callback.message.chat.id, callback.message.message_id)
        elif data == "toggle_notifications":
            await self._toggle_notifications(callback.message.chat.id, callback.message.message_id)
        elif data == "reset_account":
            await self._reset_account(callback.message.chat.id, callback.message.message_id)
        elif data == "main_menu":
            await self._send_main_menu(callback.message.chat.id, callback.message.message_id)

        await callback.answer()

    async def _send_status(self, chat_id: int, message_id: Optional[int] = None):
        """Отправка статуса трейдера"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.trader_api_url}/api/status") as response:
                    if response.status == 200:
                        data = await response.json()

                        status_emoji = "🟢" if data.get('running', False) else "🔴"
                        status_text = "Работает" if data.get('running', False) else "Остановлен"

                        equity = data.get('equity', 0)
                        unrealized_pnl = data.get('unrealized_pnl', 0)
                        total_equity = data.get('total_equity', 0)
                        positions_count = data.get('positions_count', 0)

                        pnl_emoji = "📈" if unrealized_pnl >= 0 else "📉"
                        pnl_sign = "+" if unrealized_pnl >= 0 else ""

                        text = (
                            f"📊 <b>Статус трейдера</b>\n\n"
                            f"{status_emoji} <b>Состояние:</b> {status_text}\n"
                            f"💰 <b>Капитал:</b> ${equity:.2f}\n"
                            f"{pnl_emoji} <b>Нереализованная P&L:</b> {pnl_sign}${unrealized_pnl:.2f}\n"
                            f"💎 <b>Общий капитал:</b> ${total_equity:.2f}\n"
                            f"📈 <b>Открытых позиций:</b> {positions_count}\n\n"
                            f"🕒 <i>Обновлено: {datetime.now().strftime('%H:%M:%S')}</i>"
                        )

                        keyboard = self._get_main_keyboard()

                        if message_id:
                            try:
                                await self.bot.edit_message_text(
                                    text=text,
                                    chat_id=chat_id,
                                    message_id=message_id,
                                    parse_mode="HTML",
                                    reply_markup=keyboard
                                )
                            except Exception as edit_error:
                                # Если не удалось отредактировать, отправляем новое сообщение
                                if "message is not modified" in str(edit_error):
                                    logger.debug("Сообщение не изменилось, пропускаем обновление")
                                else:
                                    logger.error(f"Ошибка редактирования сообщения: {edit_error}")
                                    await self.bot.send_message(
                                        chat_id=chat_id,
                                        text=text,
                                        parse_mode="HTML",
                                        reply_markup=keyboard
                                    )
                        else:
                            await self.bot.send_message(
                                chat_id=chat_id,
                                text=text,
                                parse_mode="HTML",
                                reply_markup=keyboard
                            )
                    else:
                        await self._send_error_message(chat_id, "Не удалось получить статус трейдера")
        except Exception as e:
            logger.error(f"Ошибка получения статуса: {e}")
            await self._send_error_message(chat_id, f"Ошибка соединения с трейдером")

    async def _send_positions(self, chat_id: int, message_id: Optional[int] = None):
        """Отправка списка открытых позиций"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.trader_api_url}/api/status") as response:
                    if response.status == 200:
                        data = await response.json()
                        positions = data.get('positions', [])

                        if not positions:
                            text = "💼 <b>Открытые позиции</b>\n\n❌ Нет открытых позиций"
                        else:
                            text = "💼 <b>Открытые позиции</b>\n\n"

                            for pos in positions:
                                pnl = pos.get('unrealized_pnl', 0)
                                pnl_emoji = "📈" if pnl >= 0 else "📉"
                                pnl_sign = "+" if pnl >= 0 else ""

                                text += (
                                    f"📊 <b>{pos['symbol']}</b>\n"
                                    f"  💎 Количество: {pos['quantity']:.2f}\n"
                                    f"  💰 Цена входа: ${pos['entry_price']:.2f}\n"
                                    f"  📊 Текущая: ${pos['current_price']:.2f}\n"
                                    f"  {pnl_emoji} P&L: {pnl_sign}${pnl:.2f}\n\n"
                                )

                        keyboard = self._get_main_keyboard()

                        if message_id:
                            try:
                                await self.bot.edit_message_text(
                                    text=text,
                                    chat_id=chat_id,
                                    message_id=message_id,
                                    parse_mode="HTML",
                                    reply_markup=keyboard
                                )
                            except Exception as edit_error:
                                if "message is not modified" in str(edit_error):
                                    logger.debug("Сообщение позиций не изменилось")
                                else:
                                    logger.error(f"Ошибка редактирования позиций: {edit_error}")
                                    await self.bot.send_message(
                                        chat_id=chat_id,
                                        text=text,
                                        parse_mode="HTML",
                                        reply_markup=keyboard
                                    )
                        else:
                            await self.bot.send_message(
                                chat_id=chat_id,
                                text=text,
                                parse_mode="HTML",
                                reply_markup=keyboard
                            )
        except Exception as e:
            logger.error(f"Ошибка получения позиций: {e}")
            await self._send_error_message(chat_id, "Ошибка получения позиций")

    async def _send_statistics(self, chat_id: int, message_id: Optional[int] = None):
        """Отправка статистики торговли"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.trader_api_url}/api/statistics") as response:
                    if response.status == 200:
                        data = await response.json()
                        stats = data.get('statistics', {})

                        total_trades = stats.get('total_trades', 0)
                        win_rate = stats.get('win_rate', 0)
                        total_pnl = stats.get('total_pnl', 0)
                        max_win = stats.get('max_win', 0)
                        max_loss = stats.get('max_loss', 0)

                        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
                        pnl_sign = "+" if total_pnl >= 0 else ""

                        text = (
                            f"📈 <b>Статистика торговли</b>\n\n"
                            f"🔢 <b>Всего сделок:</b> {total_trades}\n"
                            f"🎯 <b>Винрейт:</b> {win_rate:.1f}%\n"
                            f"{pnl_emoji} <b>Общая прибыль:</b> {pnl_sign}${total_pnl:.2f}\n"
                            f"🏆 <b>Макс. выигрыш:</b> +${max_win:.2f}\n"
                            f"💸 <b>Макс. проигрыш:</b> -${abs(max_loss):.2f}\n\n"
                            f"🕒 <i>Обновлено: {datetime.now().strftime('%H:%M:%S')}</i>"
                        )

                        keyboard = self._get_main_keyboard()

                        if message_id:
                            await self.bot.edit_message_text(
                                text=text,
                                chat_id=chat_id,
                                message_id=message_id,
                                parse_mode="HTML",
                                reply_markup=keyboard
                            )
                        else:
                            await self.bot.send_message(
                                chat_id=chat_id,
                                text=text,
                                parse_mode="HTML",
                                reply_markup=keyboard
                            )
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            await self._send_error_message(chat_id, "Ошибка получения статистики")

    async def _send_settings(self, chat_id: int, message_id: Optional[int] = None):
        """Отправка меню настроек"""
        text = (
            f"⚙️ <b>Настройки</b>\n\n"
            f"🔔 Уведомления: {'Включены' if self.notifications_enabled else 'Выключены'}\n\n"
            f"Выберите действие:"
        )

        keyboard = self._get_settings_keyboard()

        if message_id:
            await self.bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

    async def _start_trading(self, chat_id: int, message_id: Optional[int] = None):
        """Запуск торговли"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.trader_api_url}/api/start") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            await self.bot.send_message(
                                chat_id=chat_id,
                                text="✅ <b>Торговля запущена!</b>",
                                parse_mode="HTML"
                            )
                        else:
                            await self._send_error_message(chat_id, data.get('error', 'Неизвестная ошибка'))
        except Exception as e:
            logger.error(f"Ошибка запуска торговли: {e}")
            await self._send_error_message(chat_id, "Ошибка запуска торговли")

    async def _stop_trading(self, chat_id: int, message_id: Optional[int] = None):
        """Остановка торговли"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.trader_api_url}/api/stop") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            await self.bot.send_message(
                                chat_id=chat_id,
                                text="⏹️ <b>Торговля остановлена!</b>",
                                parse_mode="HTML"
                            )
                        else:
                            await self._send_error_message(chat_id, data.get('error', 'Неизвестная ошибка'))
        except Exception as e:
            logger.error(f"Ошибка остановки торговли: {e}")
            await self._send_error_message(chat_id, "Ошибка остановки торговли")

    async def _toggle_notifications(self, chat_id: int, message_id: Optional[int] = None):
        """Переключение уведомлений"""
        self.notifications_enabled = not self.notifications_enabled
        status = "включены" if self.notifications_enabled else "выключены"

        await self.bot.send_message(
            chat_id=chat_id,
            text=f"🔔 Уведомления {status}",
            parse_mode="HTML"
        )

        # Обновляем меню настроек
        await self._send_settings(chat_id, message_id)

    async def _reset_account(self, chat_id: int, message_id: Optional[int] = None):
        """Сброс счета"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.trader_api_url}/api/reset") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            await self.bot.send_message(
                                chat_id=chat_id,
                                text="🔄 <b>Счет успешно сброшен!</b>",
                                parse_mode="HTML"
                            )
                        else:
                            await self._send_error_message(chat_id, data.get('error', 'Неизвестная ошибка'))
        except Exception as e:
            logger.error(f"Ошибка сброса счета: {e}")
            await self._send_error_message(chat_id, "Ошибка сброса счета")

    async def _send_main_menu(self, chat_id: int, message_id: Optional[int] = None):
        """Отправка главного меню"""
        text = (
            "🤖 <b>Главное меню</b>\n\n"
            "Выберите действие:"
        )

        keyboard = self._get_main_keyboard()

        if message_id:
            await self.bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

    async def _send_error_message(self, chat_id: int, error_text: str):
        """Отправка сообщения об ошибке"""
        await self.bot.send_message(
            chat_id=chat_id,
            text=f"❌ <b>Ошибка:</b> {error_text}",
            parse_mode="HTML"
        )

    async def send_trade_notification(self, trade_type: str, symbol: str, quantity: float,
                                      price: float, pnl: Optional[float] = None):
        """Отправка уведомления о сделке"""
        if not self.notifications_enabled:
            return

        try:
            if trade_type.upper() == "BUY":
                emoji = "💰"
                action = "Покупка"
                text = (
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

                text = (
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

            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")

    async def send_risk_warning(self, warning_type: str, details: str):
        """Отправка предупреждения о рисках"""
        if not self.notifications_enabled:
            return

        try:
            text = (
                f"⚠️ <b>ПРЕДУПРЕЖДЕНИЕ О РИСКАХ</b>\n\n"
                f"🚨 <b>Тип:</b> {warning_type}\n"
                f"📝 <b>Детали:</b> {details}\n"
                f"🕒 <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}"
            )

            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error(f"Ошибка отправки предупреждения: {e}")

    async def monitor_positions(self):
        """Мониторинг изменений в позициях"""
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.trader_api_url}/api/status") as response:
                        if response.status == 200:
                            data = await response.json()
                            current_positions = {pos['symbol']: pos for pos in data.get('positions', [])}

                            # Проверяем новые позиции (покупки)
                            for symbol, pos in current_positions.items():
                                if symbol not in self.last_positions:
                                    await self.send_trade_notification(
                                        "BUY", symbol, pos['quantity'], pos['entry_price']
                                    )

                            # Проверяем закрытые позиции (продажи)
                            for symbol, old_pos in self.last_positions.items():
                                if symbol not in current_positions:
                                    # Получаем последнюю цену для расчета PnL
                                    # Это упрощенная версия, в реальности нужно получать данные из истории сделок
                                    await self.send_trade_notification(
                                        "SELL", symbol, old_pos['quantity'], old_pos['current_price'],
                                        old_pos.get('unrealized_pnl', 0)
                                    )

                            self.last_positions = current_positions

            except Exception as e:
                logger.error(f"Ошибка мониторинга позиций: {e}")

            await asyncio.sleep(10)  # Проверяем каждые 10 секунд

    async def start_polling(self):
        """Запуск бота"""
        logger.info("🤖 Telegram бот запущен!")

        # Запускаем мониторинг позиций в фоне
        asyncio.create_task(self.monitor_positions())

        # Запускаем polling
        await self.dp.start_polling(self.bot)


async def main():
    """Главная функция для запуска Telegram бота"""

    # Загружаем конфигурацию
    try:
        with open('telegram_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        # Создаем файл конфигурации
        config = {
            "bot_token": "YOUR_BOT_TOKEN_HERE",
            "chat_id": "YOUR_CHAT_ID_HERE",
            "trader_api_url": "http://localhost:5000"
        }

        with open('telegram_config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print("❌ Создан файл telegram_config.json")
        print("📝 Заполните bot_token и chat_id, затем запустите снова")
        return

    bot_token = config.get('bot_token')
    chat_id = config.get('chat_id')
    trader_api_url = config.get('trader_api_url', 'http://localhost:5000')

    if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
        print("❌ Укажите bot_token в telegram_config.json")
        return

    if not chat_id or chat_id == "YOUR_CHAT_ID_HERE":
        print("❌ Укажите chat_id в telegram_config.json")
        return

    # Создаем и запускаем бота
    telegram_bot = TradingTelegramBot(bot_token, chat_id, trader_api_url)
    await telegram_bot.start_polling()


if __name__ == "__main__":
    asyncio.run(main())
