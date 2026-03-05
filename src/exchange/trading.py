"""
Торговые операции Bybit: ордера, плечо, позиции, баланс.
Context7: /bybit-exchange/pybit
"""
from __future__ import annotations

from typing import Optional

from .bybit_client import BybitClient


class BybitTrading:
    """Торговые операции через Bybit API v5."""

    def __init__(self, client: BybitClient) -> None:
        self.client = client
        self.session = client.session

    def get_wallet_balance(
        self,
        account_type: str = "UNIFIED",
        coin: Optional[str] = None,
    ) -> dict:
        """Баланс кошелька. UNIFIED для perpetual."""
        kwargs = {"accountType": account_type}
        if coin:
            kwargs["coin"] = coin
        return self.session.get_wallet_balance(**kwargs)

    def get_equity_usdt(self) -> float:
        """Текущий эквити в USDT."""
        resp = self.get_wallet_balance(account_type="UNIFIED", coin="USDT")
        if resp.get("retCode") != 0:
            raise RuntimeError(f"Bybit API error: {resp.get('retMsg', 'Unknown')}")
        items = resp.get("result", {}).get("list", [])
        if not items:
            return 0.0
        coins = items[0].get("coin", [])
        for c in coins:
            if c.get("coin") == "USDT":
                return float(c.get("equity", 0) or c.get("walletBalance", 0))
        # Fallback: totalEquity
        return float(items[0].get("totalEquity", 0) or 0)

    def get_positions(
        self,
        category: str = "linear",
        symbol: Optional[str] = None,
        settle_coin: Optional[str] = None,
    ) -> dict:
        """Открытые позиции."""
        kwargs = {"category": category}
        if symbol:
            kwargs["symbol"] = symbol.upper()
        if settle_coin:
            kwargs["settleCoin"] = settle_coin
        return self.session.get_positions(**kwargs)

    def set_leverage(
        self,
        symbol: str,
        leverage: int,
        category: str = "linear",
    ) -> dict:
        """Установка плеча (1–100). One-way: buyLeverage == sellLeverage."""
        lev_str = str(min(max(leverage, 1), 100))
        return self.session.set_leverage(
            category=category,
            symbol=symbol.upper(),
            buyLeverage=lev_str,
            sellLeverage=lev_str,
        )

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: str | float,
        order_type: str = "Market",
        price: Optional[str | float] = None,
        category: str = "linear",
        reduce_only: bool = False,
        time_in_force: str = "GTC",
        position_idx: int = 0,
    ) -> dict:
        """
        Размещение ордера.

        Args:
            symbol: BTCUSDT, ETHUSDT
            side: Buy / Sell
            qty: Количество (в базовой валюте)
            order_type: Market / Limit
            price: Для Limit
            reduce_only: Только закрытие позиции
        """
        qty_str = f"{float(qty):.8f}".rstrip("0").rstrip(".")
        kwargs = {
            "category": category,
            "symbol": symbol.upper(),
            "side": side,
            "orderType": order_type,
            "qty": qty_str,
            "timeInForce": time_in_force,
            "positionIdx": position_idx,
        }
        if reduce_only:
            kwargs["reduceOnly"] = True
        if order_type == "Limit" and price is not None:
            kwargs["price"] = str(price)
        return self.session.place_order(**kwargs)

    def close_position(
        self,
        symbol: str,
        side: str,
        qty: str | float,
        category: str = "linear",
        order_type: str = "Market",
        price: Optional[str | float] = None,
        position_idx: int = 0,
    ) -> dict:
        """
        Закрытие позиции: ордер в противоположную сторону с reduceOnly.
        Long -> Sell, Short -> Buy.
        """
        return self.place_order(
            symbol=symbol,
            side=side,
            qty=qty,
            order_type=order_type,
            price=price,
            category=category,
            reduce_only=True,
            position_idx=position_idx,
        )

    def get_ticker(self, symbol: str, category: str = "linear") -> dict:
        """Текущая цена (last, bid, ask)."""
        resp = self.session.get_tickers(
            category=category,
            symbol=symbol.upper(),
        )
        if resp.get("retCode") != 0:
            raise RuntimeError(f"Bybit API error: {resp.get('retMsg', 'Unknown')}")
        items = resp.get("result", {}).get("list", [])
        return items[0] if items else {}

    def get_last_price(self, symbol: str) -> float:
        """Последняя цена."""
        t = self.get_ticker(symbol)
        return float(t.get("lastPrice", 0))
