from typing import Any, TypedDict


class SupportState(TypedDict, total=False):
    case_id: str
    thread_id: str
    created_at: str
    question: str
    order_id: str
    customer_email: str
    intent: str
    order: dict[str, Any] | None
    policy_context: list[str]
    eligibility: dict[str, Any] | None
    decision_reason: str
    proposed_action: str | None
    case_status: str
    escalation_status: str
    approval_status: str
    reviewer: str | None
    actual_action_result: dict[str, Any] | None
    email_notifications: list[dict[str, Any]]
    errors: list[str]
    answer: str
    response_source: str
    ticket: dict[str, Any] | None
