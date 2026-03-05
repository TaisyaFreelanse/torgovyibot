"""
Генератор сигналів: Long/Short entry, Signal Close, Trailing Stop.
Умови за ТЗ: MACD vs Signal + колір свічки Heiken Ashi.
Вхід на наступній свічці після виконання умов.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd

from .heiken_ashi import heiken_ashi
from .zl_macd import zero_lag_macd


class SignalType(Enum):
    NONE = "none"
    LONG_ENTRY = "long_entry"
    SHORT_ENTRY = "short_entry"
    LONG_CLOSE = "long_close"
    SHORT_CLOSE = "short_close"
    TRAILING_STOP_LONG = "trailing_stop_long"
    TRAILING_STOP_SHORT = "trailing_stop_short"


@dataclass
class StrategyParams:
    """Параметри стратегії."""
    fast_mm_period: int = 12
    slow_mm_period: int = 26
    signal_mm_period: int = 9
    use_ema: bool = True
    use_glaz_algo: bool = False
    trailing_activation_pct: float = 0.1
    trailing_stop_pct: float = 0.7


def compute_indicators(
    df: pd.DataFrame,
    params: StrategyParams,
) -> pd.DataFrame:
    """
    Обчислює Heiken Ashi та Zero Lag MACD на HA close.

    Returns:
        DataFrame з ha_*, macd_line, signal_line, is_green
    """
    ha = heiken_ashi(df)
    # MACD на close звичайних свічок (як у Pine — source=close, графік HA лише для кольору)
    # За ТЗ: "свічка Heiken Ashi показує ріст" — колір HA, але індикатор ZLMACD на close
    # У Pine при HA графіку close = HA close. Тож MACD рахуємо на close (OHLC close або HA close)
    # За стандартом: на графіку HA індикатори використовують HA-значення. Тому MACD на ha_close
    macd_df = zero_lag_macd(
        ha["ha_close"],
        fast_length=params.fast_mm_period,
        slow_length=params.slow_mm_period,
        signal_length=params.signal_mm_period,
        use_ema=params.use_ema,
        use_glaz_algo=params.use_glaz_algo,
    )
    result = pd.concat([ha, macd_df], axis=1)
    return result


def generate_signals(
    df: pd.DataFrame,
    params: StrategyParams,
    position: str = "none",  # "long" | "short" | "none"
    entry_price: Optional[float] = None,
    trail_stop: Optional[float] = None,
    allow_same_candle: bool = True,
) -> tuple[SignalType, Optional[float], Optional[float]]:
    """
    Генерує сигнал для останнього бару.

    Args:
        df: DataFrame з OHLCV (мінімум 2 бари для MACD warmup)
        params: Параметри стратегії
        position: Поточна позиція
        entry_price: Ціна входу (для trailing stop)
        trail_stop: Поточне значення trail stop
        allow_same_candle: Дозволити вхід на тій же свічці після закриття (примітка не для ШІ)

    Returns:
        (SignalType, new_entry_price, new_trail_stop)
    """
    if len(df) < 2:
        return SignalType.NONE, entry_price, trail_stop

    indicators = compute_indicators(df, params)
    if len(indicators) < 2:
        return SignalType.NONE, entry_price, trail_stop

    # Останній закритий бар (перевіряємо умови для входу на наступному)
    prev = indicators.iloc[-2]
    curr = indicators.iloc[-1]
    curr_close = float(df["close"].iloc[-1])

    macd_above = curr["macd_line"] > curr["signal_line"]
    macd_below = curr["macd_line"] < curr["signal_line"]
    is_green = curr["is_green"]
    is_red = ~is_green

    # Умови на попередньому барі (для входу на наступному)
    prev_macd_above = prev["macd_line"] > prev["signal_line"]
    prev_macd_below = prev["macd_line"] < prev["signal_line"]
    prev_green = prev["is_green"]
    prev_red = ~prev_green

    new_trail = trail_stop

    # --- Trailing Stop (пріоритет над signal close) ---
    if position == "long" and entry_price is not None and params.trailing_stop_pct > 0:
        profit_pct = (curr_close - entry_price) / entry_price * 100
        if profit_pct >= params.trailing_activation_pct:
            offset = params.trailing_stop_pct / 100 * entry_price
            if trail_stop is None:
                new_trail = curr_close - offset
            else:
                new_trail = max(trail_stop, curr_close - offset)
            if curr_close < (new_trail or 0):
                return SignalType.TRAILING_STOP_LONG, None, None

    if position == "short" and entry_price is not None and params.trailing_stop_pct > 0:
        profit_pct = (entry_price - curr_close) / entry_price * 100
        if profit_pct >= params.trailing_activation_pct:
            offset = params.trailing_stop_pct / 100 * entry_price
            if trail_stop is None:
                new_trail = curr_close + offset
            else:
                new_trail = min(trail_stop, curr_close + offset)
            if curr_close > (new_trail or 0):
                return SignalType.TRAILING_STOP_SHORT, None, None

    # --- Signal Close ---
    if position == "long" and macd_below and is_red:
        return SignalType.LONG_CLOSE, None, None
    if position == "short" and macd_above and is_green:
        return SignalType.SHORT_CLOSE, None, None

    # --- Entry ---
    # Вхід на наступній свічці: prev має умови, curr — бар входу.
    # allow_same_candle: після закриття на цій свічці — перевіряти curr для входу.
    if position == "none":
        # Long: MACD > Signal + зелена HA (на prev, або curr якщо тільки закрили)
        long_cond_prev = prev_macd_above and prev_green
        long_cond_curr = macd_above and is_green
        if (long_cond_prev and long_cond_curr) or (allow_same_candle and long_cond_curr):
            return SignalType.LONG_ENTRY, curr_close, None
        # Short: MACD < Signal + червона HA
        short_cond_prev = prev_macd_below and prev_red
        short_cond_curr = macd_below and is_red
        if (short_cond_prev and short_cond_curr) or (allow_same_candle and short_cond_curr):
            return SignalType.SHORT_ENTRY, curr_close, None

    return SignalType.NONE, entry_price, new_trail
