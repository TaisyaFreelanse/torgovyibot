"""
Кэширование свечей OHLCV для снижения количества запросов к Bybit API.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import pandas as pd

from .bybit_client import BybitClient, KLINE_LIMIT


@dataclass
class CacheEntry:
    """Запись кэша."""
    df: pd.DataFrame
    fetched_at: float
    symbol: str
    interval: str


class KlineCache:
    """
    Кэш свечей с TTL (время жизни).
    Ключ: (symbol, interval)
    """

    def __init__(
        self,
        client: BybitClient,
        ttl_seconds: int = 60,
        max_entries: int = 50,
    ) -> None:
        """
        Args:
            client: Клиент Bybit
            ttl_seconds: Время жизни кэша в секундах (обновить после истечения)
            max_entries: Максимум записей в кэше (LRU-подобное вытеснение)
        """
        self.client = client
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._cache: dict[tuple[str, str], CacheEntry] = {}
        self._access_order: list[tuple[str, str]] = []

    def _make_key(self, symbol: str, interval: str) -> tuple[str, str]:
        return (symbol.upper(), interval.strip().lower())

    def _touch(self, key: tuple[str, str]) -> None:
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        while len(self._cache) > self.max_entries and self._access_order:
            old_key = self._access_order.pop(0)
            self._cache.pop(old_key, None)

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = KLINE_LIMIT,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """
        Получает свечи: из кэша или API.

        Args:
            symbol: Символ (BTCUSDT, ETHUSDT)
            interval: Таймфрейм (5m, 15m, 1h, 4h, 1D, 1W)
            limit: Количество свечей
            force_refresh: Игнорировать кэш и запросить с API

        Returns:
            DataFrame с OHLCV
        """
        key = self._make_key(symbol, interval)
        now = time.time()

        if not force_refresh and key in self._cache:
            entry = self._cache[key]
            if now - entry.fetched_at < self.ttl:
                self._touch(key)
                return entry.df.tail(limit).copy()

        df = self.client.get_klines_df(symbol=symbol, interval=interval, limit=limit)
        self._cache[key] = CacheEntry(df=df, fetched_at=now, symbol=symbol, interval=interval)
        self._touch(key)
        return df

    def invalidate(self, symbol: str | None = None, interval: str | None = None) -> None:
        """Очищает кэш: полностью или для конкретной пары/таймфрейма."""
        if symbol is None and interval is None:
            self._cache.clear()
            self._access_order.clear()
            return

        keys_to_remove = []
        skey = symbol.upper() if symbol else None
        ikey = interval.strip().lower() if interval else None
        for (s, i) in self._cache:
            if (skey is None or s == skey) and (ikey is None or i == ikey):
                keys_to_remove.append((s, i))
        for k in keys_to_remove:
            self._cache.pop(k, None)
            if k in self._access_order:
                self._access_order.remove(k)
