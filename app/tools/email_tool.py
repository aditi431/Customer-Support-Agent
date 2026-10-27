import os
import re
import smtplib
from email.message import EmailMessage

from app.case_store import (
    claim_email_event,
    complete_email_event,
)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(address: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(address.strip()))


def send_notification(
    recipient: str,
    subject: str,
    body: str,
    dedupe_key: str
) -> dict[str, str]:
    recipient = recipient.strip()
    if not _valid_email(recipient):
        return {"status": "failed", "reason": "Invalid recipient address."}
    if not dedupe_key.strip():
        return {"status": "failed", "reason": "A notification deduplication key is required."}
    if not claim_email_event(dedupe_key):
        return {"status": "skipped", "reason": "This notification was already processed."}

    dry_run = os.getenv("EMAIL_DRY_RUN", "true").strip().lower() in {
        "1", "true", "yes", "on"
    }
    if dry_run:
        result = {
            "status": "dry_run",
            "reason": "Email preview only; no message was sent.",
            "preview": f"To: {recipient}\nSubject: {subject}\n\n{body}"
        }
        complete_email_event(dedupe_key, result["status"], result)
        return result

    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_APP_PASSWORD", "")
    port_value = os.getenv("SMTP_PORT", "587").strip()
    if not host or not username or not password:
        result = {"status": "failed", "reason": "SMTP configuration is incomplete."}
        complete_email_event(dedupe_key, result["status"], result)
        return result
    if not _valid_email(username):
        result = {"status": "failed", "reason": "SMTP_USERNAME must be a valid sender email."}
        complete_email_event(dedupe_key, result["status"], result)
        return result
    try:
        port = int(port_value)
    except ValueError:
        result = {"status": "failed", "reason": "SMTP_PORT must be an integer."}
        complete_email_event(dedupe_key, result["status"], result)
        return result
    if not 1 <= port <= 65535:
        result = {"status": "failed", "reason": "SMTP_PORT is outside the valid port range."}
        complete_email_event(dedupe_key, result["status"], result)
        return result

    message = EmailMessage()
    message["From"] = username
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        result = {
            "status": "failed",
            "reason": f"SMTP delivery failed ({type(exc).__name__})."
        }
        complete_email_event(dedupe_key, result["status"], result)
        return result

    result = {"status": "sent", "reason": "Email delivered."}
    complete_email_event(dedupe_key, result["status"], result)
    return result


def send_case_notifications(state: dict) -> list[dict[str, str]]:
    case_id = state["case_id"]
    notifications: list[dict[str, str]] = []
    status = state.get("case_status", "processing")
    email = state.get("customer_email", "").strip()

    if email:
        notifications.append(
            send_notification(
                email,
                f"Support case {case_id} received",
                (
                    "We received your support request. "
                    f"Current case status: {status.replace('_', ' ')}. "
                    "No refund has been issued."
                ),
                f"{case_id}:customer_ack"
            )
        )
    else:
        notifications.append({"status": "skipped", "reason": "No customer email was provided."})

    if state.get("escalation_status") == "escalated":
        support_email = os.getenv("SUPPORT_EMAIL", "").strip()
        if support_email:
            notifications.append(
                send_notification(
                    support_email,
                    f"Manual review required for case {case_id}",
                    (
                        f"Case {case_id} needs manual review.\n"
                        f"Intent: {state.get('intent', 'unknown')}\n"
                        f"Reason: {state.get('decision_reason', 'Review requested.')}"
                    ),
                    f"{case_id}:support_escalation"
                )
            )
        else:
            notifications.append({"status": "skipped", "reason": "SUPPORT_EMAIL is not configured."})

    return notifications
