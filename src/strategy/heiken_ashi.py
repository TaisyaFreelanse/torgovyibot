"""
Heiken Ashi — формула як у TradingView.
HA_close = (O+H+L+C)/4
HA_open = (prev_HA_open + prev_HA_close)/2
HA_high = max(H, HA_open, HA_close)
HA_low = min(L, HA_open, HA_close)
Зелена: HA_close > HA_open, червона: HA_close < HA_open
"""
from __future__ import annotations

import pandas as pd


def heiken_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Обчислює Heiken Ashi з OHLCV.

    Args:
        df: DataFrame з колонками open, high, low, close

    Returns:
        Новий DataFrame з ha_open, ha_high, ha_low, ha_close, is_green
    """
    o = df["open"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    c = df["close"].astype(float)

    ha_close = (o + h + l + c) / 4
    ha_open = pd.Series(index=df.index, dtype=float)
    ha_open.iloc[0] = (o.iloc[0] + c.iloc[0]) / 2
    for i in range(1, len(df)):
        ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2

    ha_high = pd.concat([h, ha_open, ha_close], axis=1).max(axis=1)
    ha_low = pd.concat([l, ha_open, ha_close], axis=1).min(axis=1)

    is_green = ha_close > ha_open

    return pd.DataFrame(
        {
            "ha_open": ha_open,
            "ha_high": ha_high,
            "ha_low": ha_low,
            "ha_close": ha_close,
            "is_green": is_green,
        },
        index=df.index,
    )
