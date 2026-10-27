
from app.tools.order_tool import get_order, check_refund_eligibility
from app.tools.escalation_tool import create_ticket


def test_existing_order():
    order = get_order("ORD1001")
    assert order is not None
    assert order["status"] == "Delivered"


def test_missing_order():
    assert get_order("ORD9999") is None


def test_eligible_demo_return():
    order = get_order("ORD1001")
    result = check_refund_eligibility(order)
    assert result["eligible"] is True


def test_return_outside_window():
    order = get_order("ORD1003")
    result = check_refund_eligibility(order)
    assert result["eligible"] is False


def test_general_return_within_window_does_not_require_damage():
    order = {
        "order_id": "ORD-GENERAL",
        "status": "Delivered",
        "delivery_days_ago": 5,
        "product_condition": "Opened but working"
    }
    result = check_refund_eligibility(order)
    assert result["eligible"] is True
    assert "not a refund approval" in result["reason"]


def test_ticket_creation(tmp_path, monkeypatch):
    import app.tools.escalation_tool as escalation

    monkeypatch.setattr(escalation, "TICKETS_FILE", tmp_path / "tickets.json")
    ticket = create_ticket("My case needs review", "ORD1001")

    assert ticket["ticket_id"].startswith("TKT-")
    assert ticket["status"] == "Open"
    assert (tmp_path / "tickets.json").exists()
