"""
Тест ордеров: размещение лимитного ордера (далеко от рынка) и отмена.
Не исполняет сделки — ордер не достигает рынка и сразу отменяется.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def test_place_and_cancel_order():
    """Разместить лимитный ордер далеко от рынка, затем отменить."""
    from src.exchange import BybitClient
    from src.exchange.trading import BybitTrading

    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    testnet = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
    if not api_key or not api_secret:
        print("SKIP: No BYBIT_API_KEY/SECRET")
        return

    client = BybitClient(api_key=api_key, api_secret=api_secret, testnet=testnet)
    trading = BybitTrading(client)

    symbol = "ETHUSDT"
    price = trading.get_last_price(symbol)
    # Ордер далеко от рынка: Buy на 60% ниже — не исполнится
    limit_price = str(round(price * 0.4, 2))
    qty = "0.01"  # Минимальный размер для ETH perpetual ~0.01

    print(f"Place Limit Buy {symbol} qty={qty} price={limit_price} (market ~{price:.2f})")
    resp = trading.place_order(
        symbol=symbol,
        side="Buy",
        qty=qty,
        order_type="Limit",
        price=limit_price,
    )
    assert resp.get("retCode") == 0, f"place_order failed: {resp}"
    order_id = resp.get("result", {}).get("orderId")
    print("OK: Order placed, orderId =", order_id)

    # Отмена
    cancel_resp = client.session.cancel_order(
        category="linear",
        symbol=symbol,
        orderId=order_id,
    )
    assert cancel_resp.get("retCode") == 0, f"cancel_order failed: {cancel_resp}"
    print("OK: Order cancelled")

    print("--- Order test passed ---")


def test_set_leverage():
    """Установка плеча (1x — безопасно)."""
    from src.exchange import BybitClient
    from src.exchange.trading import BybitTrading

    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    testnet = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
    if not api_key or not api_secret:
        print("SKIP: No API keys")
        return

    client = BybitClient(api_key=api_key, api_secret=api_secret, testnet=testnet)
    trading = BybitTrading(client)
    resp = trading.set_leverage("ETHUSDT", 1)
    assert resp.get("retCode") == 0, resp
    print("OK: set_leverage(ETHUSDT, 1)")
    print("--- Leverage test passed ---")


if __name__ == "__main__":
    test_place_and_cancel_order()
    test_set_leverage()
