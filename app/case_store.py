import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
CASE_DB_PATH = Path(os.getenv("CASE_DB_PATH", BASE_DIR / "data" / "cases.sqlite3"))


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    CASE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(CASE_DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_case_store() -> None:
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL UNIQUE,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS actions (
                case_id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS email_events (
                dedupe_key TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                result_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chat_requests (
                idempotency_key TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def save_case(state: dict[str, Any]) -> None:
    init_case_store()
    case_id = state.get("case_id")
    thread_id = state.get("thread_id")
    if not case_id or not thread_id:
        raise ValueError("Case ID and thread ID are required to persist a case.")

    serialized = json.dumps(state, ensure_ascii=True, default=str)
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO cases (case_id, thread_id, state_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(case_id) DO UPDATE SET
                thread_id = excluded.thread_id,
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            (case_id, thread_id, serialized, now)
        )


def get_case(case_id: str) -> dict[str, Any] | None:
    init_case_store()
    with _connect() as connection:
        row = connection.execute(
            "SELECT state_json, updated_at FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
    if not row:
        return None
    state = json.loads(row["state_json"])
    state["updated_at"] = row["updated_at"]
    return state


def get_case_by_thread(thread_id: str) -> dict[str, Any] | None:
    init_case_store()
    with _connect() as connection:
        row = connection.execute(
            "SELECT state_json, updated_at FROM cases WHERE thread_id = ?", (thread_id,)
        ).fetchone()
    if not row:
        return None
    state = json.loads(row["state_json"])
    state["updated_at"] = row["updated_at"]
    return state


def claim_chat_request(
    idempotency_key: str,
    case_id: str,
    thread_id: str
) -> tuple[dict[str, str], bool]:
    init_case_store()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO chat_requests
                (idempotency_key, case_id, thread_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (idempotency_key, case_id, thread_id, now)
        )
        row = connection.execute(
            """
            SELECT case_id, thread_id FROM chat_requests
            WHERE idempotency_key = ?
            """,
            (idempotency_key,)
        ).fetchone()
    return dict(row), cursor.rowcount == 1


def release_chat_request(idempotency_key: str, case_id: str) -> None:
    init_case_store()
    with _connect() as connection:
        connection.execute(
            """
            DELETE FROM chat_requests
            WHERE idempotency_key = ? AND case_id = ?
            """,
            (idempotency_key, case_id)
        )


def record_action_once(
    case_id: str,
    action: str,
    result: dict[str, Any]
) -> dict[str, Any]:
    init_case_store()
    now = datetime.now(timezone.utc).isoformat()
    serialized = json.dumps(result, ensure_ascii=True, default=str)
    with _connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO actions (case_id, action, result_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (case_id, action, serialized, now)
        )
        row = connection.execute(
            "SELECT result_json FROM actions WHERE case_id = ?", (case_id,)
        ).fetchone()
    return json.loads(row["result_json"])


def claim_email_event(dedupe_key: str) -> bool:
    init_case_store()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO email_events
                (dedupe_key, status, result_json, updated_at)
            VALUES (?, 'sending', '{}', ?)
            """,
            (dedupe_key, now)
        )
    return cursor.rowcount == 1


def complete_email_event(
    dedupe_key: str,
    status: str,
    result: dict[str, Any]
) -> None:
    init_case_store()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute(
            """
            UPDATE email_events
            SET status = ?, result_json = ?, updated_at = ?
            WHERE dedupe_key = ?
            """,
            (
                status,
                json.dumps(result, ensure_ascii=True, default=str),
                now,
                dedupe_key
            )
        )
