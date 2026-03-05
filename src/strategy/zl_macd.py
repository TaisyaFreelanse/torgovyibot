"""
Zero Lag MACD Enhanced 1.2 — реалізація за оригінальним кодом (veryfid, Albert Callisto).
Джерело: TradingView, оновлення 19.12.2017.
"""
from __future__ import annotations

import pandas as pd


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def zero_lag_macd(
    close: pd.Series,
    fast_length: int = 12,
    slow_length: int = 26,
    signal_length: int = 9,
    use_ema: bool = True,
    use_glaz_algo: bool = False,
) -> pd.DataFrame:
    """
    Zero Lag MACD Enhanced.

    Args:
        close: Ціна закриття (або HA close для Heiken Ashi)
        fast_length: Fast MM period
        slow_length: Slow MM period
        signal_length: Signal MM period
        use_ema: True = EMA, False = SMA (Glaz mode)
        use_glaz_algo: useOldAlgo — True = sma(ZeroLagMACD), False = (2*emasig1 - emasig2)

    Returns:
        DataFrame з macd_line, signal_line, hist
    """
    ma_fn = _ema if use_ema else _sma

    # Fast line
    ma1 = ma_fn(close, fast_length)
    ma2 = ma_fn(ma1, fast_length)
    zerolag_fast = 2 * ma1 - ma2

    # Slow line
    mas1 = ma_fn(close, slow_length)
    mas2 = ma_fn(mas1, slow_length)
    zerolag_slow = 2 * mas1 - mas2

    # MACD line
    zero_lag_macd_line = zerolag_fast - zerolag_slow

    # Signal line
    emasig1 = _ema(zero_lag_macd_line, signal_length)
    emasig2 = _ema(emasig1, signal_length)
    if use_glaz_algo:
        signal_line = _sma(zero_lag_macd_line, signal_length)
    else:
        signal_line = 2 * emasig1 - emasig2

    hist = zero_lag_macd_line - signal_line

    return pd.DataFrame(
        {
            "macd_line": zero_lag_macd_line,
            "signal_line": signal_line,
            "hist": hist,
        },
        index=close.index,
    )
