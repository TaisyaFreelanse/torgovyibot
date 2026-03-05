"""
Обработчики команд Telegram-бота.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from telegram import Update
from telegram.ext import ContextTypes

from .keyboard import get_main_menu_keyboard, get_pairs_inline_keyboard

if TYPE_CHECKING:
    from .state import BotState


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствие и меню."""
    text = (
        "🤖 <b>ZL MACD+HA+Trailing Bot</b>\n\n"
        "Оберіть дію кнопками меню внизу 👇\n\n"
        "Або команди: /status, /pairs, /config"
    )
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )


async def cmd_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    order_manager=None,
) -> None:
    """Общий статус и PnL."""
    if order_manager is None:
        await update.message.reply_text("⚠️ Торговый модуль не подключен")
        return
    try:
        balance = order_manager.get_balance()
        text = f"💰 <b>Баланс:</b> {balance:.2f} USDT"
        im_rate = order_manager.check_liquidation_risk()
        if im_rate is not None and im_rate > 0:
            text += f"\n📊 IM Rate: {im_rate:.2%}"
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_pairs(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Optional["BotState"] = None,
) -> None:
    """Список пар з кнопками Старт/Стоп."""
    if state is None:
        msg = update.message or (update.callback_query and update.callback_query.message)
        await msg.reply_text("⚠️ Состояние не инициализировано")
        return
    config = state.load_config()
    pairs = config.get("pairs", [])
    lines = []
    for p in pairs:
        sym = p.get("symbol", "?")
        tf = p.get("timeframe", "?")
        status = "✅" if state.is_pair_active(sym) else "⏸"
        lines.append(f"{status} {sym} ({tf})")
    text = "<b>Пари:</b>\n" + ("\n".join(lines) if lines else "Немає пар у конфігу")
    text += "\n\n👇 Натисніть кнопку:"
    msg = update.message or (update.callback_query and update.callback_query.message)
    keyboard = get_pairs_inline_keyboard(pairs, state)
    await msg.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def cmd_start_pair(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Optional["BotState"] = None,
) -> None:
    """Запуск торговли по паре: /start_pair ETHUSDT"""
    if state is None:
        await update.message.reply_text("⚠️ Состояние не инициализировано")
        return
    if not context.args:
        await update.message.reply_text("Использование: /start_pair ETHUSDT")
        return
    symbol = context.args[0].upper()
    state.start_pair(symbol)
    await update.message.reply_text(f"✅ Торговля запущена: {symbol}")


async def cmd_stop_pair(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Optional["BotState"] = None,
) -> None:
    """Остановка торговли по паре: /stop_pair ETHUSDT"""
    if state is None:
        await update.message.reply_text("⚠️ Состояние не инициализировано")
        return
    if not context.args:
        await update.message.reply_text("Использование: /stop_pair ETHUSDT")
        return
    symbol = context.args[0].upper()
    state.stop_pair(symbol)
    await update.message.reply_text(f"⏸ Торговля остановлена: {symbol}")


async def cmd_start_all(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Optional["BotState"] = None,
) -> None:
    """Запуск всех пар из конфига."""
    if state is None:
        await update.message.reply_text("⚠️ Состояние не инициализировано")
        return
    config = state.load_config()
    symbols = [p.get("symbol") for p in config.get("pairs", []) if p.get("symbol")]
    state.start_all(symbols)
    await update.message.reply_text(f"✅ Запущено: {', '.join(symbols) or 'нет пар'}")


async def cmd_stop_all(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Optional["BotState"] = None,
) -> None:
    """Остановка всех пар."""
    if state is None:
        await update.message.reply_text("⚠️ Состояние не инициализировано")
        return
    state.stop_all()
    await update.message.reply_text("⏸ Все пары остановлены")


async def cmd_config(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Optional["BotState"] = None,
) -> None:
    """Просмотр параметров."""
    if state is None:
        await update.message.reply_text("⚠️ Состояние не инициализировано")
        return
    config = state.load_config()
    strategy = config.get("strategy", {})
    execution = config.get("execution", {})
    lines = [
        "<b>Стратегия:</b>",
        f"  Fast: {strategy.get('fast_mm_period', '?')} | Slow: {strategy.get('slow_mm_period', '?')}",
        f"  Trailing: {strategy.get('trailing_activation_pct', '?')}% / {strategy.get('trailing_stop_pct', '?')}%",
        "<b>Исполнение:</b>",
        f"  Реинвест: {execution.get('reinvestment_pct', '?')}% | Плечо: {execution.get('leverage', '?')}x",
        f"  Лимитные: {execution.get('use_limit_orders', '?')}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_set_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Optional["BotState"] = None,
) -> None:
    """Сохранить чат для уведомлений."""
    if state is None:
        await update.message.reply_text("⚠️ Состояние не инициализировано")
        return
    chat_id = update.effective_chat.id
    state.set_chat_id(chat_id)
    await update.message.reply_text(f"✅ Чат {chat_id} збережено для сповіщень")


async def cmd_instruction(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Інструкція."""
    msg = update.message or (update.callback_query and update.callback_query.message)
    text = (
        "<b>❓ Інструкція</b>\n\n"
        "• <b>Головна</b> — баланс та статус\n"
        "• <b>Пари</b> — список пар, кнопками старт/стоп по кожній\n"
        "• <b>Запустити все</b> — старт по всіх парах з конфігу\n"
        "• <b>Зупинити все</b> — зупинка всіх пар\n"
        "• <b>Налаштування</b> — поточні параметри стратегії\n"
        "• <b>Зберегти чат</b> — для отримання сповіщень про угоди\n\n"
        "Пари та параметри змінюються у файлі config/config.yaml"
    )
    await msg.reply_text(text, parse_mode="HTML")
