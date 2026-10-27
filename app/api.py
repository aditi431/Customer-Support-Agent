import hmac
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Literal
from uuid import uuid4

from dotenv import dotenv_values, load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.case_store import (
    claim_chat_request,
    get_case,
    init_case_store,
    release_chat_request,
)
from app.graph.workflow import resume_case, run_case

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_FILE)
_PROJECT_ENV = dotenv_values(ENV_FILE)
logger = logging.getLogger("support_api")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_case_store()
    yield


app = FastAPI(
    title="AI Customer Support API",
    version="1.0.0",
    lifespan=lifespan
)

HOME_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Customer Support API</title>
  <style>
    body { font: 16px/1.6 system-ui, sans-serif; margin: 0; background: #f4f7fb; color: #172033; }
    main { max-width: 680px; margin: 12vh auto; padding: 2rem; background: white; border-radius: 12px; box-shadow: 0 8px 32px #17203318; }
    h1 { margin-top: 0; }
    a { color: #155eef; }
    code { background: #eef2f8; padding: .15rem .35rem; border-radius: 4px; }
  </style>
</head>
<body>
  <main>
    <h1>AI Customer Support API</h1>
    <p>The support service is running. Use the interactive API docs to try
    authenticated support endpoints.</p>
    <ul>
      <li><a href="/docs">API documentation</a></li>
      <li><a href="/health">Health check</a></li>
    </ul>
    <p>The customer chat UI is available separately by starting Streamlit:
    <code>python -m streamlit run app/main.py</code>.</p>
  </main>
</body>
</html>"""


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=1500)
    order_id: str = Field(default="", max_length=100)
    customer_email: str = Field(default="", max_length=254)

    @field_validator("customer_email")
    @classmethod
    def validate_customer_email(cls, value: str) -> str:
        if value and not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("A valid customer email address is required.")
        return value


class ChatResponse(BaseModel):
    case_id: str
    thread_id: str
    status: str
    answer: str
    response_source: Literal["gemini", "workflow"] = "workflow"
    approval_required: bool
    decision_reason: str = ""
    ticket_id: str | None = None


class ApprovalRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(default="", max_length=1000)


class ApprovalResponse(BaseModel):
    case_id: str
    status: str
    approval_status: str
    answer: str
    action_result: dict | None = None


def require_api_access(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("API_ACCESS_TOKEN") or _PROJECT_ENV.get("API_ACCESS_TOKEN") or ""
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="API access is not configured. Set API_ACCESS_TOKEN."
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid API access token.")


def require_staff_access(
    x_staff_token: str | None = Header(default=None),
    x_staff_id: str | None = Header(default=None)
) -> str:
    expected = os.getenv("STAFF_APPROVAL_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Staff approval is not configured."
        )
    if not x_staff_token or not hmac.compare_digest(x_staff_token, expected):
        raise HTTPException(status_code=401, detail="Invalid staff credentials.")
    staff_id = (x_staff_id or "").strip()
    if not staff_id or len(staff_id) > 100:
        raise HTTPException(status_code=401, detail="A valid staff identity is required.")
    return staff_id


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home():
    return HOME_PAGE


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(
        content=(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            '<rect width="64" height="64" rx="14" fill="#155eef"/>'
            '<path d="M15 17h34v24H31l-10 8v-8h-6z" fill="white"/>'
            '<circle cx="25" cy="29" r="2.5" fill="#155eef"/>'
            '<circle cx="32" cy="29" r="2.5" fill="#155eef"/>'
            '<circle cx="39" cy="29" r="2.5" fill="#155eef"/>'
            '</svg>'
        ),
        media_type="image/svg+xml"
    )


def _chat_response(state: dict, interrupted: bool | None = None) -> ChatResponse:
    approval_required = (
        state.get("case_status") == "awaiting_approval"
        if interrupted is None
        else interrupted
    )
    answer = state.get("answer") or (
        "Your case is awaiting human review. No refund has been issued."
        if approval_required
        else "Your support request has been recorded."
    )
    ticket = state.get("ticket") or {}
    return ChatResponse(
        case_id=state["case_id"],
        thread_id=state["thread_id"],
        status=state.get("case_status", "processing"),
        answer=answer,
        response_source=state.get("response_source", "workflow"),
        approval_required=approval_required,
        decision_reason=state.get("decision_reason", ""),
        ticket_id=ticket.get("ticket_id")
    )


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    dependencies=[Depends(require_api_access)]
)
def chat(
    request: ChatRequest,
    response: Response,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=128
    )
):
    idempotency_key = idempotency_key.strip()
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key cannot be blank.")
    reservation, created = claim_chat_request(
        idempotency_key,
        str(uuid4()),
        str(uuid4())
    )
    if not created:
        existing_case = get_case(reservation["case_id"])
        if existing_case is None:
            raise HTTPException(
                status_code=409,
                detail="This request is already being processed."
            )
        if existing_case.get("case_status") == "processing":
            raise HTTPException(
                status_code=409,
                detail="This request is still processing; check its status shortly."
            )
        response.headers["Idempotent-Replay"] = "true"
        return _chat_response(existing_case)

    try:
        state = run_case(
            request.question,
            request.order_id,
            request.customer_email,
            case_id=reservation["case_id"],
            thread_id=reservation["thread_id"]
        )
    except Exception as exc:
        if get_case(reservation["case_id"]) is None:
            release_chat_request(idempotency_key, reservation["case_id"])
        logger.error("Case processing failed (%s).", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="The support workflow could not process this request."
        ) from exc

    return _chat_response(state, bool(state.get("__interrupt__")))


@app.get(
    "/api/cases/{case_id}",
    dependencies=[Depends(require_api_access)]
)
def read_case(case_id: str):
    case = get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case


@app.get(
    "/api/cases/{case_id}/status",
    dependencies=[Depends(require_api_access)]
)
def read_case_status(case_id: str):
    case = get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return {
        "case_id": case["case_id"],
        "thread_id": case["thread_id"],
        "status": case.get("case_status"),
        "approval_status": case.get("approval_status"),
        "escalation_status": case.get("escalation_status"),
        "updated_at": case.get("updated_at")
    }


@app.post(
    "/api/cases/{case_id}/approval",
    response_model=ApprovalResponse
)
def decide_case(
    case_id: str,
    request: ApprovalRequest,
    staff_id: str = Depends(require_staff_access)
):
    case = get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    if case.get("case_status") != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail="This case is not waiting for approval."
        )
    try:
        result = resume_case(
            case,
            request.decision,
            staff_id,
            request.reason
        )
    except Exception as exc:
        logger.error("Approval processing failed (%s).", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="The approval decision could not be processed."
        ) from exc

    if result.get("__interrupt__"):
        raise HTTPException(
            status_code=409,
            detail="The workflow remains paused and requires review."
        )
    return ApprovalResponse(
        case_id=case_id,
        status=result.get("case_status", "unknown"),
        approval_status=result.get("approval_status", "unknown"),
        answer=result.get("answer", ""),
        action_result=result.get("actual_action_result")
    )
