import smtplib

import app.case_store as case_store
import app.tools.email_tool as email_tool


def test_email_dry_run_previews_without_smtp(tmp_path, monkeypatch):
    monkeypatch.setattr(case_store, "CASE_DB_PATH", tmp_path / "cases.sqlite3")
    monkeypatch.setenv("EMAIL_DRY_RUN", "true")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("SMTP must not be used in dry-run mode.")

    monkeypatch.setattr(email_tool.smtplib, "SMTP", fail_if_called)
    result = email_tool.send_notification(
        "customer@example.com",
        "Case received",
        "We received your request.",
        "case-1:ack"
    )

    assert result["status"] == "dry_run"
    assert "customer@example.com" in result["preview"]


def test_email_failure_is_recorded_and_not_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(case_store, "CASE_DB_PATH", tmp_path / "cases.sqlite3")
    monkeypatch.setenv("EMAIL_DRY_RUN", "false")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "test-only")
    calls = []

    class BrokenSMTP:
        def __init__(self, *args, **kwargs):
            calls.append("connect")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            raise smtplib.SMTPException("private smtp detail")

    monkeypatch.setattr(email_tool.smtplib, "SMTP", BrokenSMTP)
    first = email_tool.send_notification(
        "customer@example.com", "Case update", "Update", "case-2:update"
    )
    second = email_tool.send_notification(
        "customer@example.com", "Case update", "Update", "case-2:update"
    )

    assert first["status"] == "failed"
    assert "private smtp detail" not in str(first)
    assert second["status"] == "skipped"
    assert calls == ["connect"]


def test_invalid_recipient_does_not_claim_notification(tmp_path, monkeypatch):
    monkeypatch.setattr(case_store, "CASE_DB_PATH", tmp_path / "cases.sqlite3")
    result = email_tool.send_notification(
        "not-an-email", "Case update", "Update", "case-3:update"
    )
    assert result["status"] == "failed"
    assert "Invalid recipient" in result["reason"]
