import operator
from typing import Annotated, Literal, TypedDict


class RunState(TypedDict, total=False):
    run_id: str
    prompt: str
    source: Literal["ui", "slack", "worker"]
    intent: str
    intent_args: dict
    clock_offset_days: int
    dry_run_sends: bool
    invoices: list[dict]
    results: Annotated[list[dict], operator.add]
    answer: str | None
    summary: dict | None


class InvoiceState(TypedDict, total=False):
    run_id: str
    invoice: dict
    client: dict
    thread: list[dict]
    signal: dict
    facts: dict
    severity: dict
    decision: str
    rule_id: str
    reasons: list[str]
    counterfactuals: list[str]
    plan: list[dict]
    messages: dict
    approvals: dict
    results: list[dict]
