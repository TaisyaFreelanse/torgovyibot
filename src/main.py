"""
Точка входа торгового бота ZL MACD+HA+Trailing.
"""
import logging
import os

from dotenv import load_dotenv

from src.telegram import run_bot

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def main() -> None:
    """Запуск бота: Telegram + торговый цикл (этап 6)."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Укажите TELEGRAM_BOT_TOKEN в .env")
        return
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    testnet = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
    run_bot(
        token=token,
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet,
    )


if __name__ == "__main__":
    main()
