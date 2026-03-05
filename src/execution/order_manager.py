"""
Менеджер ордеров: расчёт размера, размещение лимитных ордеров,
закрытие, установка плеча, конвертация в USDT.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from src.exchange.bybit_client import BybitClient
from src.exchange.trading import BybitTrading
from src.execution.position_sizer import calc_position_qty, round_qty


# Скидка/надбавка к цене для лимитного ордера (в %)
LIMIT_ORDER_OFFSET_PCT = 0.02


@dataclass
class ExecutionParams:
    """Параметры исполнения."""
    reinvestment_pct: float = 100
    leverage: int = 1
    use_limit_orders: bool = True
    convert_to_usdt: bool = True
    limit_offset_pct: float = LIMIT_ORDER_OFFSET_PCT


class OrderManager:
    """Управление ордерами и позициями."""

    def __init__(
        self,
        client: BybitClient,
        params: ExecutionParams,
        on_liquidation_warning: Optional[Callable[[str, float], None]] = None,
    ) -> None:
        self.client = client
        self.trading = BybitTrading(client)
        self.params = params
        self.on_liquidation_warning = on_liquidation_warning

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        """Установка плеча перед открытием позиции."""
        return self.trading.set_leverage(symbol=symbol, leverage=leverage)

    def get_balance(self) -> float:
        """Доступный эквити в USDT."""
        return self.trading.get_equity_usdt()

    def get_position_size(self, symbol: str) -> Optional[tuple[str, float]]:
        """
        Размер открытой позиции.
        Returns:
            (side, qty) или None
        """
        resp = self.trading.get_positions(category="linear", symbol=symbol)
        if resp.get("retCode") != 0:
            return None
        items = resp.get("result", {}).get("list", [])
        for p in items:
            size = float(p.get("size", 0))
            if size > 0:
                return (p.get("side", "Buy"), size)
        return None

    def calc_qty(self, symbol: str) -> float:
        """Рассчитывает qty для новой позиции."""
        balance = self.get_balance()
        price = self.trading.get_last_price(symbol)
        raw_qty = calc_position_qty(
            balance_usdt=balance,
            price=price,
            reinvestment_pct=self.params.reinvestment_pct,
            leverage=self.params.leverage,
        )
        return round_qty(raw_qty)

    def _limit_price(self, symbol: str, side: str, reference_price: float) -> str:
        """Цена для лимитного ордера (с небольшим offset)."""
        offset = reference_price * (self.params.limit_offset_pct / 100)
        if side == "Buy":
            return f"{reference_price - offset:.2f}"
        return f"{reference_price + offset:.2f}"

    def open_long(
        self,
        symbol: str,
        qty: Optional[float] = None,
    ) -> dict:
        """Открытие лонг позиции."""
        self.set_leverage(symbol, self.params.leverage)
        qty = qty or self.calc_qty(symbol)
        if qty <= 0:
            return {"retCode": 1, "retMsg": "Insufficient balance or invalid qty"}
        price = self.trading.get_last_price(symbol)
        order_type = "Limit" if self.params.use_limit_orders else "Market"
        price_param = self._limit_price(symbol, "Buy", price) if order_type == "Limit" else None
        return self.trading.place_order(
            symbol=symbol,
            side="Buy",
            qty=qty,
            order_type=order_type,
            price=price_param,
        )

    def open_short(
        self,
        symbol: str,
        qty: Optional[float] = None,
    ) -> dict:
        """Открытие шорт позиции."""
        self.set_leverage(symbol, self.params.leverage)
        qty = qty or self.calc_qty(symbol)
        if qty <= 0:
            return {"retCode": 1, "retMsg": "Insufficient balance or invalid qty"}
        price = self.trading.get_last_price(symbol)
        order_type = "Limit" if self.params.use_limit_orders else "Market"
        price_param = self._limit_price(symbol, "Sell", price) if order_type == "Limit" else None
        return self.trading.place_order(
            symbol=symbol,
            side="Sell",
            qty=qty,
            order_type=order_type,
            price=price_param,
        )

    def close_position_by_signal(
        self,
        symbol: str,
        side: str,
        qty: float,
    ) -> dict:
        """
        Закрытие позиции по сигналу (limit или market).
        side: противоположный позиции — Long -> Sell, Short -> Buy
        """
        close_side = "Sell" if side.lower() == "long" else "Buy"
        order_type = "Limit" if self.params.use_limit_orders else "Market"
        price = self.trading.get_last_price(symbol) if order_type == "Limit" else None
        price_str = self._limit_price(symbol, close_side, price) if price else None
        return self.trading.close_position(
            symbol=symbol,
            side=close_side,
            qty=qty,
            order_type=order_type,
            price=price_str,
        )

    def close_position_trailing(
        self,
        symbol: str,
        side: str,
        qty: float,
        trigger_price: float,
    ) -> dict:
        """
        Закрытие по трейлинг-стопу.
        Используем market для надёжности при срабатывании стопа.
        """
        close_side = "Sell" if side.lower() == "long" else "Buy"
        return self.trading.close_position(
            symbol=symbol,
            side=close_side,
            qty=qty,
            order_type="Market",
        )

    def convert_to_usdt(self, symbol: str) -> dict:
        """
        После закрытия — конвертация в USDT.
        Для linear perpetual (ETHUSDT, BTCUSDT) маржа уже в USDT — no-op.
        Для spot или USDC пар — нужна конвертация (отдельная логика).
        """
        if not self.params.convert_to_usdt:
            return {"retCode": 0, "retMsg": "Skipped"}
        if "USDT" in symbol.upper():
            return {"retCode": 0, "retMsg": "Already USDT-margined"}
        # TODO: spot convert для пар с USDC/другим quote
        return {"retCode": 0, "retMsg": "No conversion needed for perpetual"}

    def check_liquidation_risk(self, symbol: Optional[str] = None) -> Optional[float]:
        """
        Проверка риска ликвидации (accountIMRate).
        При IM rate > 0.8 — предупреждение.
        Returns:
            accountIMRate или None
        """
        resp = self.trading.get_wallet_balance(account_type="UNIFIED")
        if resp.get("retCode") != 0:
            return None
        items = resp.get("result", {}).get("list", [])
        if not items:
            return None
        im_rate = float(items[0].get("accountIMRate", 0) or 0)
        if im_rate > 0.8 and self.on_liquidation_warning:
            self.on_liquidation_warning(symbol or "account", im_rate)
        return im_rate
