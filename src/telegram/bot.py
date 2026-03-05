"""
Telegram-бот: инициализация, регистрация команд, запуск.
"""
from __future__ import annotations

import logging
from typing import Optional

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from src.execution.order_manager import OrderManager
from src.exchange.bybit_client import BybitClient

from .handlers import (
    cmd_config,
    cmd_instruction,
    cmd_pairs,
    cmd_set_chat,
    cmd_start,
    cmd_start_all,
    cmd_start_pair,
    cmd_status,
    cmd_stop_all,
    cmd_stop_pair,
)
from .keyboard import get_main_menu_keyboard
from .state import BotState

logger = logging.getLogger(__name__)


def create_handlers(state: BotState, order_manager: Optional[OrderManager] = None):
    """Фабрики обработчиков с инжектом state и order_manager."""

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await cmd_start(update, context)

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await cmd_status(update, context, order_manager=order_manager)

    async def pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await cmd_pairs(update, context, state=state)

    async def start_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await cmd_start_pair(update, context, state=state)

    async def stop_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await cmd_stop_pair(update, context, state=state)

    async def start_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await cmd_start_all(update, context, state=state)

    async def stop_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await cmd_stop_all(update, context, state=state)

    async def config(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await cmd_config(update, context, state=state)

    async def set_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await cmd_set_chat(update, context, state=state)

    async def instruction(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await cmd_instruction(update, context)

    async def menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробка натискань кнопок меню."""
        msg = update.message or update.edited_message
        if not msg or not msg.text:
            return
        text = msg.text.strip()
        if text == "📊 Головна / Статус":
            await status(update, context)
        elif text == "📋 Пари":
            await pairs(update, context)
        elif text == "⚙️ Налаштування":
            await config(update, context)
        elif text == "▶️ Запустити все":
            await start_all(update, context)
        elif text == "⏸️ Зупинити все":
            await stop_all(update, context)
        elif text == "📢 Зберегти чат":
            await set_chat(update, context)
        elif text == "❓ Інструкція":
            await instruction(update, context)

    async def callback_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробка інлайн-кнопок (Старт/Стоп пари)."""
        query = update.callback_query
        await query.answer()
        data = query.data
        if data.startswith("start_"):
            symbol = data.replace("start_", "")
            state.start_pair(symbol)
            await query.edit_message_text(f"✅ Торговля запущена: {symbol}")
        elif data.startswith("stop_"):
            symbol = data.replace("stop_", "")
            state.stop_pair(symbol)
            await query.edit_message_text(f"⏸ Торговля зупинена: {symbol}")

    return {
        "start": start,
        "status": status,
        "pairs": pairs,
        "start_pair": start_pair,
        "stop_pair": stop_pair,
        "start_all": start_all,
        "stop_all": stop_all,
        "config": config,
        "set_chat": set_chat,
        "instruction": instruction,
        "menu_button": menu_button,
        "callback_button": callback_button,
    }


def build_application(
    token: str,
    state: BotState,
    order_manager: Optional[OrderManager] = None,
) -> Application:
    """Сборка Application с командами."""
    app = Application.builder().token(token).build()
    handlers = create_handlers(state, order_manager)
    app.add_handler(CommandHandler("start", handlers["start"]))
    app.add_handler(CommandHandler("status", handlers["status"]))
    app.add_handler(CommandHandler("pairs", handlers["pairs"]))
    app.add_handler(CommandHandler("start_pair", handlers["start_pair"]))
    app.add_handler(CommandHandler("stop_pair", handlers["stop_pair"]))
    app.add_handler(CommandHandler("start_all", handlers["start_all"]))
    app.add_handler(CommandHandler("stop_all", handlers["stop_all"]))
    app.add_handler(CommandHandler("config", handlers["config"]))
    app.add_handler(CommandHandler("set_chat", handlers["set_chat"]))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers["menu_button"]))
    app.add_handler(CallbackQueryHandler(handlers["callback_button"]))
    app.bot_data["state"] = state
    app.bot_data["order_manager"] = order_manager
    return app


def run_bot(
    token: str,
    config_path: str = "config/config.yaml",
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    testnet: bool = False,
    start_runner: bool = True,
) -> None:
    """
    Запуск Telegram-бота + торговый цикл (опционально).
    OrderManager создаётся при наличии api_key/api_secret.
    Graceful shutdown: Ctrl+C останавливает runner, затем бота.
    """
    import threading

    from src.runner import TradingRunner
    from src.telegram.notifier import Notifier

    state = BotState(config_path)
    order_manager = None
    client = None
    if api_key and api_secret:
        client = BybitClient(api_key=api_key, api_secret=api_secret, testnet=testnet)
        from src.execution import ExecutionParams

        config = state.load_config()
        exec_cfg = config.get("execution", {})
        params = ExecutionParams(
            reinvestment_pct=exec_cfg.get("reinvestment_pct", 100),
            leverage=exec_cfg.get("leverage", 1),
            use_limit_orders=exec_cfg.get("use_limit_orders", True),
            convert_to_usdt=exec_cfg.get("convert_to_usdt", True),
        )
        order_manager = OrderManager(client, params)

    app = build_application(token, state, order_manager)
    runner = None

    if start_runner and order_manager and client:
        stop_event = threading.Event()
        notifier = Notifier(app.bot)
        if state.chat_id:
            notifier.set_chat_id(state.chat_id)
        runner = TradingRunner(
            state=state,
            order_manager=order_manager,
            client=client,
            config_path=config_path,
            notifier=notifier,
            stop_event=stop_event,
        )
        runner.start()

    logger.info("Telegram bot starting...")
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        if runner:
            runner.stop()
