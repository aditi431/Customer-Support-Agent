import sqlite3
from types import SimpleNamespace

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

import app.case_store as case_store
import app.graph.workflow as workflow
import app.tools.escalation_tool as escalation


def _make_graph(monkeypatch, tmp_path, retrieved=None):
    monkeypatch.setattr(case_store, "CASE_DB_PATH", tmp_path / "cases.sqlite3")
    monkeypatch.setattr(escalation, "TICKETS_FILE", tmp_path / "tickets.json")
    monkeypatch.setattr(workflow, "client", None)
    monkeypatch.setattr(
        workflow,
        "retrieve_policy",
        lambda query, top_k: retrieved if retrieved is not None else [
            {"text": "Return requests can be made within 7 days.", "score": 0.9}
        ]
    )
    return workflow.build_graph(MemorySaver())


def _invoke(graph, question, order_id="", thread_id="thread-1"):
    state = {
        "case_id": "case-1",
        "thread_id": thread_id,
        "question": question,
        "order_id": order_id,
        "customer_email": ""
    }
    return graph.invoke(
        state,
        config={"configurable": {"thread_id": thread_id}}
    )


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Can I get my money back?", "refund"),
        ("The product is damaged, can I return it?", "return"),
        ("Where is my shipped order?", "order_status"),
        ("What is the return policy?", "policy_question"),
        ("What is the status of my return?", "return"),
        ("hello", "greeting"),
        ("Hello, I need help", "greeting"),
        ("Hello, where is my order?", "order_status"),
        ("ORD1001", "order_id"),
        ("I need help with something else", "other")
    ]
)
def test_classifies_customer_intent(question, expected):
    assert workflow.classify_intent(question) == expected


def test_eligible_case_pauses_and_resumes_with_staff_approval(monkeypatch, tmp_path):
    graph = _make_graph(monkeypatch, tmp_path)
    config = {"configurable": {"thread_id": "thread-approve"}}
    initial = graph.invoke(
        {
            "case_id": "case-approve",
            "thread_id": "thread-approve",
            "question": "The item is wrong. Can I return it?",
            "order_id": "ORD1001",
            "customer_email": ""
        },
        config=config
    )

    assert initial["case_status"] == "awaiting_approval"
    assert initial["approval_status"] == "pending"
    assert initial["__interrupt__"]

    resumed = graph.invoke(
        Command(resume={
            "decision": "approve",
            "reviewer": "staff-1",
            "reason": "Checked the order record."
        }),
        config=config
    )

    assert resumed["case_status"] == "approved_demo"
    assert resumed["approval_status"] == "approved"
    assert resumed["reviewer"] == "staff-1"
    assert resumed["actual_action_result"]["status"] == "simulated_only"
    assert "no return, refund" in resumed["actual_action_result"]["message"].lower()
    assert case_store.get_case("case-approve")["case_status"] == "approved_demo"


def test_rejected_approval_does_not_execute_action(monkeypatch, tmp_path):
    graph = _make_graph(monkeypatch, tmp_path)
    config = {"configurable": {"thread_id": "thread-reject"}}
    initial = graph.invoke(
        {
            "case_id": "case-reject",
            "thread_id": "thread-reject",
            "question": "Can I return this wrong product?",
            "order_id": "ORD1001",
            "customer_email": ""
        },
        config=config
    )
    assert initial["__interrupt__"]

    resumed = graph.invoke(
        Command(resume={
            "decision": "reject",
            "reviewer": "staff-2",
            "reason": "Needs more information."
        }),
        config=config
    )

    assert resumed["case_status"] == "rejected"
    assert resumed["approval_status"] == "rejected"
    assert resumed.get("actual_action_result") is None


def test_sqlite_checkpoint_resumes_paused_case(monkeypatch, tmp_path):
    monkeypatch.setattr(case_store, "CASE_DB_PATH", tmp_path / "cases.sqlite3")
    monkeypatch.setattr(escalation, "TICKETS_FILE", tmp_path / "tickets.json")
    monkeypatch.setattr(workflow, "client", None)
    monkeypatch.setattr(
        workflow,
        "retrieve_policy",
        lambda query, top_k: [{"text": "Return requests are within 7 days.", "score": 0.9}]
    )
    connection = sqlite3.connect(
        str(tmp_path / "checkpoints.sqlite3"),
        check_same_thread=False
    )
    try:
        checkpointer = SqliteSaver(connection)
        checkpointer.setup()
        graph = workflow.build_graph(checkpointer)
        config = {"configurable": {"thread_id": "sqlite-thread"}}
        paused = graph.invoke(
            {
                "case_id": "sqlite-case",
                "thread_id": "sqlite-thread",
                "question": "Can I return the wrong item?",
                "order_id": "ORD1001",
                "customer_email": ""
            },
            config=config
        )
        assert paused["__interrupt__"]

        resumed = graph.invoke(
            Command(resume={
                "decision": "reject",
                "reviewer": "sqlite-reviewer",
                "reason": "Demo test"
            }),
            config=config
        )
    finally:
        connection.close()

    assert resumed["approval_status"] == "rejected"
    assert resumed["case_status"] == "rejected"


def test_missing_order_id_prompts_customer(monkeypatch, tmp_path):
    graph = _make_graph(monkeypatch, tmp_path)
    result = _invoke(graph, "Can I return a damaged item?")

    assert result["case_status"] == "needs_order_id"
    assert "order ID" in result["answer"]


def test_greeting_gets_gemini_reply_without_escalation(monkeypatch, tmp_path):
    graph = _make_graph(monkeypatch, tmp_path)
    requests = []

    class FakeModels:
        def generate_content(self, **kwargs):
            requests.append(kwargs)
            return SimpleNamespace(
                function_calls=[],
                text="Hello! How can I help you today?"
            )

    monkeypatch.setattr(
        workflow,
        "client",
        SimpleNamespace(models=FakeModels())
    )
    result = _invoke(graph, "hello")

    assert result["intent"] == "greeting"
    assert result["case_status"] == "resolved"
    assert result["escalation_status"] == "not_required"
    assert result.get("ticket") is None
    assert result["answer"] == "Hello! How can I help you today?"
    assert result["response_source"] == "gemini"
    assert len(requests) == 1


def test_order_id_only_message_looks_up_order_without_escalation(monkeypatch, tmp_path):
    graph = _make_graph(monkeypatch, tmp_path)
    result = _invoke(graph, "ORD1001")

    assert result["intent"] == "order_id"
    assert result["order_id"] == "ORD1001"
    assert result["order"]["order_id"] == "ORD1001"
    assert result["case_status"] == "resolved"
    assert result["escalation_status"] == "not_required"
    assert result.get("ticket") is None


def test_order_id_in_customer_message_is_used_for_order_lookup(monkeypatch, tmp_path):
    graph = _make_graph(monkeypatch, tmp_path)
    result = _invoke(
        graph,
        "My order Id is ORD1001, and issue is that wrong item has placed"
    )

    assert result["order_id"] == "ORD1001"
    assert result["order"]["order_id"] == "ORD1001"
    assert result["case_status"] == "awaiting_approval"


def test_general_policy_question_does_not_require_order_id(monkeypatch, tmp_path):
    graph = _make_graph(monkeypatch, tmp_path)
    result = _invoke(graph, "What is the return policy?")

    assert result["case_status"] == "resolved"
    assert "7 days" in result["answer"]


def test_unknown_order_is_escalated(monkeypatch, tmp_path):
    graph = _make_graph(monkeypatch, tmp_path)
    result = _invoke(graph, "Where is my order?", "ORD9999")

    assert result["case_status"] == "escalated"
    assert result["ticket"]["case_id"] == "case-1"


def test_policy_retrieval_failure_is_escalated(monkeypatch, tmp_path):
    graph = _make_graph(monkeypatch, tmp_path)

    def fail_retrieval(query, top_k):
        raise RuntimeError("private test detail")

    monkeypatch.setattr(workflow, "retrieve_policy", fail_retrieval)
    result = _invoke(graph, "Can I return this?", "ORD1001")

    assert result["case_status"] == "escalated"
    assert any("Policy retrieval failed" in error for error in result["errors"])
    assert "private test detail" not in str(result)


def test_already_refunded_order_cannot_create_second_proposal(monkeypatch, tmp_path):
    graph = _make_graph(monkeypatch, tmp_path)
    monkeypatch.setattr(
        workflow,
        "get_order",
        lambda order_id: {
            "order_id": order_id,
            "status": "Delivered",
            "delivery_days_ago": 3,
            "product_condition": "Damaged",
            "refund_status": "Refunded"
        }
    )
    result = _invoke(graph, "I want a refund", "ORD1001")

    assert result["case_status"] == "resolved"
    assert result["proposed_action"] is None
    assert "completed refund" in result["decision_reason"]


def test_order_status_uses_verified_order_when_policy_search_is_empty(
    monkeypatch,
    tmp_path
):
    graph = _make_graph(monkeypatch, tmp_path, retrieved=[])
    result = _invoke(graph, "Where is my order?", "ORD1002")

    assert result["case_status"] == "resolved"
    assert result["order"]["status"] == "Shipped"


def test_gemini_agent_executes_tool_calls(monkeypatch):
    calls = [
        SimpleNamespace(name="retrieve_policy", args={"query": "return window"}),
        SimpleNamespace(name="check_return_eligibility", args={"order_id": "ORD1001"})
    ]
    responses = [
        SimpleNamespace(
            function_calls=calls,
            candidates=[SimpleNamespace(content="tool calls")],
            text=None
        ),
        SimpleNamespace(function_calls=[], candidates=[], text="Your order may qualify.")
    ]
    requests = []

    class FakeModels:
        def generate_content(self, **kwargs):
            requests.append(kwargs)
            return responses.pop(0)

    monkeypatch.setattr(
        workflow,
        "client",
        SimpleNamespace(models=FakeModels())
    )
    monkeypatch.setattr(
        workflow,
        "retrieve_policy",
        lambda query, top_k: [
            {"text": "Returns are requested within seven days.", "score": 0.9}
        ]
    )
    state = {
        "question": "Can I return this damaged item?",
        "intent": "return",
        "case_status": "resolved",
        "decision_reason": "Checking the return.",
        "policy_context": [],
        "order_id": "ORD1001",
        "order": None,
        "eligibility": None,
        "approval_status": "not_required",
        "actual_action_result": None
    }

    result = workflow._generate_response(state)

    assert result["answer"] == "Your order may qualify."
    assert result["response_source"] == "gemini"
    assert result["policy_context"] == ["Returns are requested within seven days."]
    assert result["order"]["order_id"] == "ORD1001"
    assert result["eligibility"]["eligible"] is True
    assert len(requests) == 2
    assert requests[0]["config"].tools[0].function_declarations
    assert any(
        content.role == "tool"
        for content in requests[1]["contents"]
        if hasattr(content, "role")
    )


def test_gemini_cannot_lookup_an_order_other_than_the_customer_order(monkeypatch):
    monkeypatch.setattr(workflow, "get_order", lambda order_id: {
        "order_id": order_id
    })
    state = {"question": "Check my order", "order_id": "ORD1001", "order": None}

    result = workflow._execute_agent_tool(
        "lookup_order",
        {"order_id": "ORD1002"},
        state
    )

    assert result["error"] == "Only the customer-provided order ID can be checked."
    assert state["order"] is None


def test_gemini_refund_completion_claim_is_replaced_with_safe_response(monkeypatch):
    class FakeModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(
                function_calls=[],
                text="Your refund has been processed and sent."
            )

    monkeypatch.setattr(
        workflow,
        "client",
        SimpleNamespace(models=FakeModels())
    )
    state = {
        "question": "Can I get a refund?",
        "intent": "refund",
        "case_status": "resolved",
        "decision_reason": "Eligibility checked.",
        "policy_context": ["Refunds follow inspection."],
        "order_id": "ORD1001",
        "order": {"order_id": "ORD1001", "refund_status": "Not requested"},
        "eligibility": {"eligible": True, "reason": "Meets demo checks."},
        "approval_status": "not_required",
        "actual_action_result": None
    }

    result = workflow._generate_response(state)

    assert "processed and sent" not in result["answer"]
    assert "has been issued" not in result["answer"]


def test_ticket_creation_is_idempotent_for_same_case(tmp_path, monkeypatch):
    monkeypatch.setattr(escalation, "TICKETS_FILE", tmp_path / "tickets.json")
    first = escalation.create_ticket("Review this case", "ORD1001", "case-idem")
    second = escalation.create_ticket("Review this case", "ORD1001", "case-idem")

    assert first == second
    assert len(__import__("json").loads((tmp_path / "tickets.json").read_text())) == 1


def test_streamlit_compatibility_wrapper_passes_optional_email(monkeypatch):
    captured = {}

    def fake_run_case(question, order_id, customer_email):
        captured.update({
            "question": question,
            "order_id": order_id,
            "customer_email": customer_email
        })
        return {
            "answer": "Case received.",
            "policy_context": [],
            "email_notifications": [{"status": "dry_run"}],
            "case_id": "case-ui",
            "case_status": "resolved"
        }

    monkeypatch.setattr(workflow, "run_case", fake_run_case)
    result = workflow.answer_customer(
        "Where is my order?",
        "ORD1001",
        "customer@example.com"
    )

    assert captured["customer_email"] == "customer@example.com"
    assert result["email_notifications"] == [{"status": "dry_run"}]
    assert result["answer"] == "Case received."
