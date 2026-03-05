"""
Отправка уведомлений: сделки, ликвидация, остановка.
"""
from __future__ import annotations

import urllib.request
import urllib.parse
import json
from typing import Optional

from telegram import Bot


def _sync_send(token: str, chat_id: int, text: str) -> bool:
    """Синхронная отправка в Telegram (для вызова из потоков)."""
    if not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


class Notifier:
    """Уведомления в Telegram."""

    def __init__(self, bot: Bot, chat_id: Optional[int] = None) -> None:
        self.bot = bot
        self._chat_id = chat_id

    def set_chat_id(self, chat_id: int) -> None:
        self._chat_id = chat_id

    async def send(self, text: str, chat_id: Optional[int] = None) -> bool:
        """Отправить сообщение."""
        cid = chat_id or self._chat_id
        if not cid:
            return False
        try:
            await self.bot.send_message(chat_id=cid, text=text, parse_mode="HTML")
            return True
        except Exception:
            return False

    async def trade_opened(self, symbol: str, side: str, price: float, qty: float, chat_id: Optional[int] = None) -> None:
        msg = f"📈 <b>Открыта позиция</b>\n{symbol} {side}\nЦена: {price}\nQty: {qty}"
        await self.send(msg, chat_id)

    async def trade_closed(self, symbol: str, side: str, price: float, pnl: Optional[float], chat_id: Optional[int] = None) -> None:
        pnl_str = f"PnL: {pnl:.2f} USDT" if pnl is not None else ""
        msg = f"📉 <b>Закрыта позиция</b>\n{symbol} {side}\nЦена: {price}\n{pnl_str}"
        await self.send(msg, chat_id)

    async def liquidation_warning(self, symbol: str, im_rate: float, chat_id: Optional[int] = None) -> None:
        msg = f"⚠️ <b>Риск ликвидации!</b>\n{symbol}\nIM Rate: {im_rate:.2%}"
        await self.send(msg, chat_id)

    async def trading_stopped(self, reason: str, chat_id: Optional[int] = None) -> None:
        msg = f"🛑 <b>Торговля остановлена</b>\n{reason}"
        await self.send(msg, chat_id)

    def sync_send_text(self, text: str, chat_id: Optional[int] = None) -> bool:
        """Синхронная отправка (для вызова из торгового потока)."""
        cid = chat_id or self._chat_id
        if not cid:
            return False
        token = getattr(self.bot, "token", None) or getattr(self.bot, "_token", None)
        if not token:
            return False
        return _sync_send(str(token), cid, text)
