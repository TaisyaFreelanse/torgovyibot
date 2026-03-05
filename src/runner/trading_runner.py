"""
Торговый цикл: воркеры по парам, опрос сигналов, исполнение.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from src.exchange import BybitClient, KlineCache
from src.execution.order_manager import OrderManager
from src.strategy import StrategyParams, SignalType, generate_signals
from src.telegram import BotState
from src.telegram.notifier import Notifier

logger = logging.getLogger(__name__)

# Интервал опроса (секунды)
POLL_INTERVAL = 60


class TradingRunner:
    """
    Торговый цикл. Запускается в отдельном потоке.
    Для каждой активной пары: получает свечи, генерирует сигналы, исполняет.
    """

    def __init__(
        self,
        state: BotState,
        order_manager: OrderManager,
        client: BybitClient,
        config_path: str = "config/config.yaml",
        poll_interval: int = POLL_INTERVAL,
        notifier: Optional[Notifier] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        self.state = state
        self.order_manager = order_manager
        self.kline_cache = KlineCache(client, ttl_seconds=30)
        self.config_path = config_path
        self.poll_interval = poll_interval
        self.notifier = notifier
        self.stop_event = stop_event or threading.Event()
        self._strategy_params: Optional[StrategyParams] = None
        self._thread: Optional[threading.Thread] = None

    def _load_params(self) -> StrategyParams:
        if self._strategy_params is None:
            config = self.state.load_config()
            s = config.get("strategy", {})
            self._strategy_params = StrategyParams(
                fast_mm_period=s.get("fast_mm_period", 12),
                slow_mm_period=s.get("slow_mm_period", 26),
                signal_mm_period=s.get("signal_mm_period", 9),
                use_ema=s.get("use_ema", True),
                use_glaz_algo=s.get("use_glaz_algo", False),
                trailing_activation_pct=s.get("trailing_activation_pct", 0.1),
                trailing_stop_pct=s.get("trailing_stop_pct", 0.7),
            )
        return self._strategy_params

    def _get_pair_config(self) -> list[tuple[str, str, float | None]]:
        """(symbol, timeframe, max_usdt) для активных пар из конфига."""
        config = self.state.load_config()
        pairs = config.get("pairs", [])
        active = self.state.active_pairs
        return [
            (
                p["symbol"],
                p.get("timeframe", "1h"),
                p.get("max_usdt"),  # None = использовать reinvestment_pct от баланса
            )
            for p in pairs
            if p.get("symbol") in active
        ]

    def _get_position_info(self, symbol: str) -> tuple[str, float, Optional[float]]:
        """(side, qty, avg_price) или (none, 0, None)."""
        pos = self.order_manager.get_position_size(symbol)
        if not pos:
            return ("none", 0.0, None)
        side, qty = pos
        resp = self.order_manager.trading.get_positions(category="linear", symbol=symbol)
        items = resp.get("result", {}).get("list", [])
        avg_price = None
        for p in items:
            if float(p.get("size", 0)) > 0:
                avg_price = float(p.get("avgPrice", 0) or p.get("avgEntryPrice", 0))
                break
        return (side, qty, avg_price)

    def _process_pair(
        self, symbol: str, timeframe: str, max_usdt: float | None = None
    ) -> None:
        """Один цикл обработки пары. max_usdt — лимит маржи в USDT для этой пары."""
        try:
            df = self.kline_cache.get_klines(symbol, timeframe, limit=100)
            if len(df) < 50:
                return
            params = self._load_params()
            position, qty, entry_price = self._get_position_info(symbol)
            pos_str = "none" if position == "none" else ("long" if position == "Buy" else "short")
            trail_stop = None  # TODO: persist trail_stop per pair
            sig, new_entry, new_trail = generate_signals(
                df, params,
                position=pos_str,
                entry_price=entry_price,
                trail_stop=trail_stop,
            )
            if sig == SignalType.NONE:
                return
            curr_price = float(df["close"].iloc[-1])
            if sig == SignalType.LONG_ENTRY and position == "none":
                resp = self.order_manager.open_long(symbol, max_usdt=max_usdt)
                if resp.get("retCode") == 0 and self.notifier:
                    self.notifier.sync_send_text(f"📈 Long {symbol} @ {curr_price}")
            elif sig == SignalType.SHORT_ENTRY and position == "none":
                resp = self.order_manager.open_short(symbol, max_usdt=max_usdt)
                if resp.get("retCode") == 0 and self.notifier:
                    self.notifier.sync_send_text(f"📉 Short {symbol} @ {curr_price}")
            elif sig == SignalType.LONG_CLOSE and position == "Buy":
                resp = self.order_manager.close_position_by_signal(symbol, "Long", qty)
                if resp.get("retCode") == 0:
                    if entry_price is not None and max_usdt is not None:
                        self.order_manager.on_position_closed(
                            symbol, "Long", qty, entry_price, curr_price,
                        )
                    self.order_manager.convert_to_usdt(symbol)
                    if self.notifier:
                        self.notifier.sync_send_text(f"📉 Close Long {symbol} @ {curr_price}")
            elif sig == SignalType.SHORT_CLOSE and position == "Sell":
                resp = self.order_manager.close_position_by_signal(symbol, "Short", qty)
                if resp.get("retCode") == 0:
                    if entry_price is not None and max_usdt is not None:
                        self.order_manager.on_position_closed(
                            symbol, "Short", qty, entry_price, curr_price,
                        )
                    self.order_manager.convert_to_usdt(symbol)
                    if self.notifier:
                        self.notifier.sync_send_text(f"📈 Close Short {symbol} @ {curr_price}")
            elif sig in (SignalType.TRAILING_STOP_LONG, SignalType.TRAILING_STOP_SHORT):
                side = "Long" if sig == SignalType.TRAILING_STOP_LONG else "Short"
                resp = self.order_manager.close_position_trailing(symbol, side, qty, curr_price)
                if resp.get("retCode") == 0 and entry_price is not None and max_usdt is not None:
                    self.order_manager.on_position_closed(
                        symbol, side, qty, entry_price, curr_price,
                    )
                if self.notifier:
                    self.notifier.sync_send_text(f"🛑 Trailing Stop {side} {symbol} @ {curr_price}")
        except Exception as e:
            logger.exception("Pair %s error: %s", symbol, e)

    def _run_loop(self) -> None:
        """Основной цикл."""
        logger.info("Trading runner started")
        while not self.stop_event.is_set():
            try:
                pairs = self._get_pair_config()
                for symbol, timeframe, max_usdt in pairs:
                    if self.stop_event.is_set():
                        break
                    self._process_pair(symbol, timeframe, max_usdt)
                    time.sleep(2)  # Throttle между парами
            except Exception as e:
                logger.exception("Runner loop error: %s", e)
            self.stop_event.wait(self.poll_interval)
        logger.info("Trading runner stopped")

    def start(self) -> None:
        """Запуск в фоновом потоке."""
        if self._thread and self._thread.is_alive():
            return
        self.stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Остановка."""
        self.stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
