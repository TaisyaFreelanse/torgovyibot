"""
Bybit API v5 client — получение OHLCV (kline) для perpetual.
Документация: https://bybit-exchange.github.io/docs/v5/market/kline
Context7: /bybit-exchange/pybit
"""
from __future__ import annotations

import time
from typing import Optional

import pandas as pd
from pybit.unified_trading import HTTP

# Маппинг таймфреймов: конфиг -> Bybit API interval
# Bybit: 1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M
TIMEFRAME_MAP = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "3h": "120",
    "4h": "240",
    "6h": "360",
    "12h": "720",
    "1D": "D",
    "1d": "D",
    "1W": "W",
    "1w": "W",
}

# Максимум свечей за один запрос Bybit
KLINE_LIMIT = 200


class BybitClient:
    """Клиент Bybit для получения рыночных данных."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False,
        recv_window: int = 15000,
    ) -> None:
        """
        Args:
            api_key: API ключ (опционально для публичных endpoints)
            api_secret: API секрет (опционально)
            testnet: Использовать testnet Bybit
            recv_window: Окно времени для запросов (мс). 15000 по умолчанию —
                        помогает при рассинхронизации часов (ErrCode 10002).
        """
        self.session = HTTP(
            testnet=testnet,
            api_key=api_key or "",
            api_secret=api_secret or "",
            recv_window=recv_window,
        )
        self.testnet = testnet

    def get_interval(self, timeframe: str) -> str:
        """Преобразует таймфрейм в формат Bybit API."""
        tf = timeframe.strip()
        return TIMEFRAME_MAP.get(tf, TIMEFRAME_MAP.get(tf.lower(), tf))

    def get_kline(
        self,
        symbol: str,
        interval: str,
        category: str = "linear",
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: int = KLINE_LIMIT,
    ) -> dict:
        """
        Получает свечи (kline) для perpetual.

        Args:
            symbol: Символ (BTCUSDT, ETHUSDT, ...)
            interval: Таймфрейм (5m, 15m, 1h, 4h, 1D, 1W и т.д.)
            category: linear (USDT perpetual), inverse, spot
            start: Начальный timestamp (ms)
            end: Конечный timestamp (ms)
            limit: Количество свечей (макс 1000)

        Returns:
            Сырой ответ API: {retCode, result: {list: [[ts, o, h, l, c, vol, turnover], ...]}}
        """
        bybit_interval = self.get_interval(interval)
        kwargs = {
            "category": category,
            "symbol": symbol.upper(),
            "interval": bybit_interval,
            "limit": min(limit, 1000),
        }
        if start is not None:
            kwargs["start"] = start
        if end is not None:
            kwargs["end"] = end

        return self.session.get_kline(**kwargs)

    def get_klines_df(
        self,
        symbol: str,
        interval: str,
        limit: int = KLINE_LIMIT,
        category: str = "linear",
    ) -> pd.DataFrame:
        """
        Получает свечи и возвращает DataFrame.

        Returns:
            DataFrame с колонками: timestamp, open, high, low, close, volume
            Сортировка: от старых к новым (ascending)
        """
        resp = self.get_kline(symbol=symbol, interval=interval, limit=limit, category=category)
        if resp.get("retCode") != 0:
            raise RuntimeError(f"Bybit API error: {resp.get('retMsg', 'Unknown')}")

        items = resp.get("result", {}).get("list", [])
        if not items:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        # Формат: [startTime, open, high, low, close, volume, turnover]
        df = pd.DataFrame(
            items,
            columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"],
        )
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df
