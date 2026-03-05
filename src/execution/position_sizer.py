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
) -> float:
    """
    Рассчитывает количество (qty) для открытия позиции.

    Args:
        balance_usdt: Доступный баланс в USDT
        price: Текущая цена актива
        reinvestment_pct: % от баланса (1–100)
        leverage: Плечо (1–100)

    Returns:
        Qty в базовой валюте (например, BTC)
    """
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
