"""
Расчёт размера позиции: % реинвестирования, плечо.
Размер = (balance * reinvestment_pct/100) * leverage / price
"""
from __future__ import annotations


def calc_position_qty(
    balance_usdt: float,
    price: float,
    reinvestment_pct: float = 100,
    leverage: int = 1,
    max_usdt: float | None = None,
    allocated_capital: float | None = None,
) -> float:
    """
    Рассчитывает количество (qty) для открытия позиции.

    Args:
        balance_usdt: Доступный баланс в USDT
        price: Текущая цена актива
        reinvestment_pct: % от баланса (1–100) — для пар без max_usdt
        leverage: Плечо (1–100)
        max_usdt: Стартовый капитал на пару (только для первой сделки)
        allocated_capital: Текущий выделенный капитал (для реинвеста, без лимита)

    Returns:
        Qty в базовой валюте (например, BTC)
    """
    if allocated_capital is not None and allocated_capital > 0:
        margin = min(allocated_capital, balance_usdt)
    elif max_usdt is not None and max_usdt > 0:
        margin = min(max_usdt, balance_usdt)
    else:
        margin = balance_usdt * (reinvestment_pct / 100)
    position_value = margin * leverage
    if price <= 0:
        return 0.0
    return position_value / price


def round_qty(qty: float, min_qty: float = 1e-8, qty_step: float = 1e-5) -> float:
    """
    Округляет qty до допустимого шага (lot size).
    По умолчанию — консервативное округление вниз.
    """
    if qty < min_qty:
        return 0.0
    steps = int(qty / qty_step)
    return steps * qty_step
