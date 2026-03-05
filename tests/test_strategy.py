"""Тесты стратегии."""
import pandas as pd
from src.strategy import (
    heiken_ashi,
    zero_lag_macd,
    StrategyParams,
    compute_indicators,
    generate_signals,
    SignalType,
)


def test_heiken_ashi():
    """Проверка Heiken Ashi."""
    df = pd.DataFrame({
        "open": [100, 102, 101, 105],
        "high": [103, 104, 106, 108],
        "low": [99, 101, 100, 104],
        "close": [102, 103, 105, 106],
    })
    ha = heiken_ashi(df)
    assert "ha_open" in ha.columns
    assert "ha_close" in ha.columns
    assert "is_green" in ha.columns
    assert len(ha) == len(df)


def test_zero_lag_macd():
    """Проверка Zero Lag MACD."""
    close = pd.Series([100 + i * 0.5 + (i % 3) for i in range(100)])
    macd = zero_lag_macd(close, fast_length=12, slow_length=26, signal_length=9)
    assert "macd_line" in macd.columns
    assert "signal_line" in macd.columns
    assert len(macd) == len(close)


def test_generate_signals():
    """Проверка генерации сигналов."""
    # Генерируем тестовые OHLCV
    n = 50
    df = pd.DataFrame({
        "timestamp": range(n),
        "open": 100 + pd.Series(range(n)) * 0.1,
        "high": 101 + pd.Series(range(n)) * 0.1,
        "low": 99 + pd.Series(range(n)) * 0.1,
        "close": 100 + pd.Series(range(n)) * 0.1,
    })
    params = StrategyParams()
    sig, entry, trail = generate_signals(df, params, position="none")
    assert sig in SignalType
    assert sig != SignalType.NONE or entry is None
