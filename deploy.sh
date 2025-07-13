#!/bin/bash

# Скрипт для быстрого обновления торгового бота

set -e

echo "🔄 Обновление торгового бота..."

# Переход в директорию проекта
cd /home/$USER/trader

# Остановка сервисов
echo "⏹️ Остановка сервисов..."
sudo systemctl stop trading-web trading-telegram

# Бекап текущих конфигураций
echo "💾 Создание бекапа конфигураций..."
cp telegram_config.json telegram_config.json.backup
cp trading_config.json trading_config.json.backup

# Обновление кода
echo "📥 Получение обновлений..."
git pull origin main

# Восстановление конфигураций
echo "🔧 Восстановление конфигураций..."
cp telegram_config.json.backup telegram_config.json
cp trading_config.json.backup trading_config.json

# Обновление зависимостей
echo "📦 Обновление зависимостей..."
source venv/bin/activate
pip install -r requirements.txt

# Запуск сервисов
echo "▶️ Запуск сервисов..."
sudo systemctl start trading-web trading-telegram

# Проверка статуса
echo "✅ Проверка статуса..."
sleep 5
sudo systemctl status trading-web --no-pager
sudo systemctl status trading-telegram --no-pager

echo "🎉 Обновление завершено!"

# Показать статус
echo ""
echo "📊 Статус сервисов:"
sudo systemctl is-active trading-web trading-telegram

echo ""
echo "🌐 Ваш сайт доступен по адресу: https://$(hostname -f)"
echo "📱 Отправьте /start вашему Telegram боту для проверки"
