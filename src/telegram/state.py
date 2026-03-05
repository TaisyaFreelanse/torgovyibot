"""
Состояние бота: активные пары, конфиг, доступ для уведомлений.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml


class BotState:
    """Состояние бота: активные пары, chat_id для уведомлений."""

    def __init__(self, config_path: str | Path = "config/config.yaml") -> None:
        self.config_path = Path(config_path)
        self._active_pairs: set[str] = set()
        self._chat_id: Optional[int] = None

    @property
    def active_pairs(self) -> set[str]:
        return self._active_pairs.copy()

    def is_pair_active(self, symbol: str) -> bool:
        return symbol.upper() in self._active_pairs

    def start_pair(self, symbol: str) -> None:
        self._active_pairs.add(symbol.upper())

    def stop_pair(self, symbol: str) -> None:
        self._active_pairs.discard(symbol.upper())

    def start_all(self, symbols: list[str]) -> None:
        for s in symbols:
            self._active_pairs.add(s.upper())

    def stop_all(self) -> None:
        self._active_pairs.clear()

    def set_chat_id(self, chat_id: int) -> None:
        self._chat_id = chat_id

    @property
    def chat_id(self) -> Optional[int]:
        if self._chat_id:
            return self._chat_id
        try:
            return int(os.environ.get("TELEGRAM_CHAT_ID", "0") or "0") or None
        except (ValueError, TypeError):
            return None

    def load_config(self) -> dict:
        if not self.config_path.exists():
            return {}
        with open(self.config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_config(self, data: dict) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
