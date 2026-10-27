import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.api as api
import app.case_store as case_store


def test_chat_request_validates_customer_email():
    with pytest.raises(ValidationError):
        api.ChatRequest(
            question="Where is my order?",
            customer_email="invalid"
        )


def test_chat_request_rejects_blank_or_oversized_questions():
    with pytest.raises(ValidationError):
        api.ChatRequest(question="   ")
    with pytest.raises(ValidationError):
        api.ChatRequest(question="q" * 1501)


def test_api_access_requires_configured_matching_token(monkeypatch):
    monkeypatch.delenv("API_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(api, "_PROJECT_ENV", {})
    with pytest.raises(HTTPException) as missing:
        api.require_api_access("client-token")
    assert missing.value.status_code == 503

    monkeypatch.setenv("API_ACCESS_TOKEN", "expected-token")
    with pytest.raises(HTTPException) as invalid:
        api.require_api_access("incorrect-token")
    assert invalid.value.status_code == 401

    assert api.require_api_access("expected-token") is None


def test_api_access_uses_project_env_when_process_variable_is_empty(monkeypatch):
    monkeypatch.setenv("API_ACCESS_TOKEN", "")
    monkeypatch.setattr(api, "_PROJECT_ENV", {"API_ACCESS_TOKEN": "project-token"})

    assert api.require_api_access("project-token") is None


def test_staff_access_requires_separate_token_and_identity(monkeypatch):
    monkeypatch.setenv("STAFF_APPROVAL_TOKEN", "staff-secret")
    with pytest.raises(HTTPException) as invalid:
        api.require_staff_access("staff-secret", None)
    assert invalid.value.status_code == 401
    assert api.require_staff_access("staff-secret", "staff-1") == "staff-1"


def test_api_health_and_chat_authentication(tmp_path, monkeypatch):
    monkeypatch.setattr(case_store, "CASE_DB_PATH", tmp_path / "cases.sqlite3")
    monkeypatch.setenv("API_ACCESS_TOKEN", "api-secret")
    run_calls = []

    def fake_run_case(question, order_id, customer_email, *, case_id, thread_id):
        run_calls.append((question, case_id, thread_id))
        state = {
            "case_id": case_id,
            "thread_id": thread_id,
            "case_status": "resolved",
            "answer": "Order is delivered.",
            "decision_reason": "Verified demo order."
        }
        case_store.save_case(state)
        return state

    monkeypatch.setattr(
        api,
        "run_case",
        fake_run_case
    )
    with TestClient(api.app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        home = client.get("/")
        assert home.status_code == 200
        assert "AI Customer Support API" in home.text
        assert "/docs" in home.text
        favicon = client.get("/favicon.ico")
        assert favicon.status_code == 200
        assert favicon.headers["content-type"].startswith("image/svg+xml")
        denied = client.post(
            "/api/chat",
            headers={"Idempotency-Key": "chat-1"},
            json={"question": "Where is my order?", "order_id": "ORD1001"}
        )
        assert denied.status_code == 401
        accepted = client.post(
            "/api/chat",
            headers={
                "X-API-Key": "api-secret",
                "Idempotency-Key": "chat-1"
            },
            json={"question": "Where is my order?", "order_id": "ORD1001"}
        )
        replay = client.post(
            "/api/chat",
            headers={
                "X-API-Key": "api-secret",
                "Idempotency-Key": "chat-1"
            },
            json={"question": "Where is my order?", "order_id": "ORD1001"}
        )
        assert accepted.status_code == 200
        assert replay.status_code == 200
        assert replay.headers["Idempotent-Replay"] == "true"
        assert accepted.json()["case_id"] == replay.json()["case_id"]
        assert len(run_calls) == 1


def test_case_read_requires_api_token(tmp_path, monkeypatch):
    monkeypatch.setattr(case_store, "CASE_DB_PATH", tmp_path / "cases.sqlite3")
    monkeypatch.setenv("API_ACCESS_TOKEN", "api-secret")
    case_store.save_case({
        "case_id": "case-read",
        "thread_id": "thread-read",
        "case_status": "resolved",
        "customer_email": "customer@example.com"
    })
    with TestClient(api.app) as client:
        response = client.get("/api/cases/case-read")
    assert response.status_code == 401


def test_approval_api_requires_staff_token_and_records_staff_identity(
    tmp_path,
    monkeypatch
):
    monkeypatch.setattr(case_store, "CASE_DB_PATH", tmp_path / "cases.sqlite3")
    monkeypatch.setenv("STAFF_APPROVAL_TOKEN", "staff-secret")
    case_store.save_case({
        "case_id": "case-approval-api",
        "thread_id": "thread-approval-api",
        "case_status": "awaiting_approval",
        "approval_status": "pending"
    })
    monkeypatch.setattr(
        api,
        "resume_case",
        lambda case, decision, reviewer, reason: {
            "case_status": "approved_demo",
            "approval_status": "approved",
            "answer": "Approved for demo review only.",
            "actual_action_result": {"status": "simulated_only"}
        }
    )
    with TestClient(api.app) as client:
        denied = client.post(
            "/api/cases/case-approval-api/approval",
            json={"decision": "approve"}
        )
        accepted = client.post(
            "/api/cases/case-approval-api/approval",
            headers={
                "X-Staff-Token": "staff-secret",
                "X-Staff-Id": "reviewer-1"
            },
            json={"decision": "approve", "reason": "Policy checked."}
        )
    assert denied.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["action_result"]["status"] == "simulated_only"
