# Trading Bot ZL MACD+HA+Trailing

Торговый бот для Bybit с стратегией на основе Zero Lag MACD Enhanced, Heiken Ashi и трейлинг-стопа.

## Установка

```bash
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

## Настройка

1. Скопируйте `.env.example` в `.env`
2. Заполните `BYBIT_API_KEY`, `BYBIT_API_SECRET`, `TELEGRAM_BOT_TOKEN`
3. Настройте пары и параметры в `config/config.yaml`

## Запуск

```bash
python -m src.main
```

## Структура проекта

```
torgovyibot/
├── src/
│   ├── exchange/    # Bybit API
│   ├── strategy/    # ZL MACD, Heiken Ashi, сигналы
│   ├── execution/   # Ордера, конвертация
│   ├── telegram/    # Telegram bot
│   └── main.py
├── config/
│   └── config.yaml
├── tests/
├── .env.example
└── requirements.txt
```
