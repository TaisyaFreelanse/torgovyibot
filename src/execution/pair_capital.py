"""
Зберігання виділеного капіталу по парах для реінвестування.
Перша угода — ліміт max_usdt. Далі капітал зростає за рахунок reinvestment_pct % прибутку.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = Path("data/pair_capital.json")


class PairCapitalStore:
    """
    Зберігає allocated_capital по парах.
    Перша угода: max_usdt. Потім += profit * reinvestment_pct/100 (або -= loss).
    """

    def __init__(self, store_path: Path | str = DEFAULT_STORE_PATH) -> None:
        self.store_path = Path(store_path)
        self._data: dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        """Завантажити з файлу."""
        if not self.store_path.exists():
            self._data = {}
            return
        try:
            with open(self.store_path, encoding="utf-8") as f:
                self._data = {k: float(v) for k, v in json.load(f).items()}
        except Exception as e:
            logger.warning("Could not load pair capital: %s", e)
            self._data = {}

    def _save(self) -> None:
        """Зберегти у файл."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.warning("Could not save pair capital: %s", e)

    def get_allocated(self, symbol: str, max_usdt: float | None) -> float:
        """
        Отримати виділений капітал для пари.
        Якщо пари ще немає — ініціалізувати max_usdt (перша угода).
        Якщо капітал 0 (після збитку) — перезапуск з max_usdt.
        """
        symbol = symbol.upper()
        if max_usdt is None:
            return 0.0  # для пар без max_usdt не використовуємо цей store
        if symbol in self._data:
            val = max(0.0, self._data[symbol])
            if val <= 0 and max_usdt > 0:
                self._data[symbol] = max_usdt
                self._save()
                return max_usdt
            return val
        # Перша угода — початковий капітал
        self._data[symbol] = max_usdt
        self._save()
        return max_usdt

    def on_close(
        self,
        symbol: str,
        profit_usdt: float,
        reinvestment_pct: float,
    ) -> None:
        """
        Оновити капітал після закриття позиції.
        profit_usdt: прибуток/збиток у USDT (від'ємний при збитку).
        reinvestment_pct: % прибутку для реінвестування (1–100). При збитку капітал зменшується.
        """
        symbol = symbol.upper()
        if symbol not in self._data:
            return  # пара без max_usdt — не оновлюємо
        current = self._data[symbol]
        if profit_usdt >= 0:
            reinvested = profit_usdt * (reinvestment_pct / 100)
            self._data[symbol] = current + reinvested
        else:
            self._data[symbol] = current + profit_usdt  # збиток зменшує капітал
        self._data[symbol] = max(0.0, self._data[symbol])
        self._save()
        logger.info(
            "Pair %s capital: %.2f -> %.2f (profit=%.2f, reinvest_pct=%.0f)",
            symbol, current, self._data[symbol], profit_usdt, reinvestment_pct,
        )
