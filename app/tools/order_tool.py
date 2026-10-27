
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
ORDERS_FILE = BASE_DIR / "data" / "orders.json"


def get_order(order_id: str):
    if not order_id or not order_id.strip():
        return None

    orders = json.loads(ORDERS_FILE.read_text(encoding="utf-8"))
    target = order_id.strip().upper()

    for order in orders:
        if order["order_id"].upper() == target:
            return order

    return None


def check_refund_eligibility(order: dict):
    if not order:
        return {
            "eligible": False,
            "reason": "Order not found. Please verify the order ID."
        }

    days = order.get("delivery_days_ago")

    if order.get("status") != "Delivered":
        return {
            "eligible": False,
            "reason": "The order is not marked as delivered."
        }

    if days is None:
        return {
            "eligible": False,
            "reason": "Delivery date is unavailable."
        }

    if days < 0:
        return {
            "eligible": False,
            "reason": "Invalid delivery date in the demo record."
        }

    if days > 7:
        return {
            "eligible": False,
            "reason": "The demo policy allows return requests within 7 days of delivery."
        }

    return {
        "eligible": True,
        "reason": (
            "The order appears to be within the policy's 7-day return-request "
            "window. This is not a refund approval; refunds follow receipt and inspection."
        )
    }
