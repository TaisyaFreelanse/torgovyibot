"""Тесты слоя исполнения."""
from src.execution import ExecutionParams, calc_position_qty, round_qty


def test_calc_position_qty():
    """Расчёт qty."""
    qty = calc_position_qty(balance_usdt=1000, price=50000, reinvestment_pct=50, leverage=2)
    assert qty > 0
    # margin=500, position_value=1000, qty=1000/50000=0.02
    assert abs(qty - 0.02) < 0.0001


def test_round_qty():
    """Округление qty."""
    assert round_qty(0.0012345, qty_step=0.001) == 0.001
    assert round_qty(0.0001, min_qty=0.001) == 0.0
