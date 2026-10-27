
import json
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parents[2]
TICKETS_FILE = BASE_DIR / "data" / "tickets.json"


def create_ticket(question: str, order_id: str = "", case_id: str = ""):
    if not question.strip():
        raise ValueError("Question cannot be empty.")

    if TICKETS_FILE.exists():
        tickets = json.loads(TICKETS_FILE.read_text(encoding="utf-8"))
    else:
        tickets = []

    if case_id:
        existing = next(
            (item for item in tickets if item.get("case_id") == case_id),
            None
        )
        if existing:
            return existing

    ticket = {
        "ticket_id": f"TKT-{uuid4().hex[:8].upper()}",
        "case_id": case_id,
        "question": question.strip(),
        "order_id": order_id.strip().upper(),
        "status": "Open",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    tickets.append(ticket)
    TICKETS_FILE.write_text(
        json.dumps(tickets, indent=2),
        encoding="utf-8"
    )

    return ticket
