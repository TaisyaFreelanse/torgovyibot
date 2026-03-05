"""
Клавіатура меню — кнопки як у боті комунальних платежів.
"""
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Головне меню — постійні кнопки внизу чату."""
    keyboard = [
        [KeyboardButton("📊 Головна / Статус")],
        [KeyboardButton("📋 Пари"), KeyboardButton("⚙️ Налаштування")],
        [KeyboardButton("▶️ Запустити все"), KeyboardButton("⏸️ Зупинити все")],
        [KeyboardButton("📢 Зберегти чат"), KeyboardButton("❓ Інструкція")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_pairs_inline_keyboard(pairs: list, state) -> InlineKeyboardMarkup:
    """Інлайн-кнопки для кожної пари: Старт / Стоп."""
    buttons = []
    for p in pairs:
        sym = p.get("symbol", "?")
        tf = p.get("timeframe", "?")
        is_active = state.is_pair_active(sym) if state else False
        if is_active:
            buttons.append([InlineKeyboardButton(f"⏸ {sym} ({tf})", callback_data=f"stop_{sym}")])
        else:
            buttons.append([InlineKeyboardButton(f"▶ {sym} ({tf})", callback_data=f"start_{sym}")])
    if not buttons:
        return None
    return InlineKeyboardMarkup(buttons)
