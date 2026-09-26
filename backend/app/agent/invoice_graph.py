"""The per-invoice decision sub-graph: read_thread -> interpret -> build_facts ->
score -> decide -> counterfactuals -> plan_actions -> write_messages ->
governance_gate -> execute -> record_trace.

Every node is a pure-ish async function of (InvoiceState, Runtime[GraphContext]) ->
partial state update; LangGraph merges the update back into state. Reasoning-layer
calls (interpret/write_message/explain_decision) already fall back to deterministic
behaviour on any LLM failure, so this graph never needs its own try/except around them.
"""

import json
from datetime import date, datetime

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app.agent import thread as thread_module
from app.agent.context import GraphContext
from app.agent.executor_node import execute_action, state_for_decision
from app.agent.schemas import GmailMessage
from app.agent.sense import workspace_ids
from app.agent.state import InvoiceState
from app.business import get_business_config
from app.integrations import notion, slack
from app.money import format_inr
from app.policy.facts import InvoiceFacts, ResponseSignal, build_facts
from app.policy.router import PlannedAction, route
from app.policy.rules import counterfactuals as compute_counterfactuals
from app.policy.rules import evaluate
from app.policy.severity import score_severity
from app.reasoning.explainer import explain_decision
from app.reasoning.interpreter import interpret
from app.reasoning.schemas import WriterBrief
from app.reasoning.writer import write_message
from app.swy.executor import CallCtx

DEFAULT_TONE = {
    "gmail_thank_you": "thankful",
    "gmail_reminder": "gentle",
    "gmail_escalation": "serious-respectful",
    "gmail_acknowledgment": "apologetic",
    "gmail_reconcile_request": "gentle",
}
MESSAGE_CHANNEL_BY_TOOL = {
    "gmail.send": "email",
    "jira.issue.create": "jira",
    "slack.post": "slack",
    "twilio.sms.send": "sms",
}


async def read_thread_node(state: InvoiceState, runtime: Runtime[GraphContext]) -> dict:
    ctx = CallCtx(run_id=state["run_id"], invoice_id=state["invoice"]["id"], node="read_thread")
    messages = await thread_module.fetch_client_thread(state["client"]["email"], ctx=ctx)
    relevant = thread_module.messages_for_invoice(messages, state["invoice"]["number"])
    return {"thread": [m.model_dump(mode="json") for m in relevant]}


async def interpret_node(state: InvoiceState, runtime: Runtime[GraphContext]) -> dict:
    context = runtime.context
    messages = [GmailMessage.model_validate(m) for m in state["thread"]]
    since_raw = state["memory"].get("last_client_msg_at")
    since = datetime.fromisoformat(since_raw) if since_raw else None
    unseen = thread_module.unseen_client_messages(messages, since)

    msg_date = unseen[-1].date.isoformat() if unseen else context.clock.now().isoformat()
    signal = await interpret(
        [m.body for m in unseen], msg_date, db=context.db, cache=context.llm_cache
    )

    update: dict = {"signal": signal.model_dump(mode="json")}
    if unseen:
        memory = dict(state["memory"])
        memory["last_client_msg_at"] = unseen[-1].date.isoformat()
        if signal.category == "PROMISE_TO_PAY" and signal.promise_date:
            memory["promise_date"] = signal.promise_date.isoformat()
            memory["promise_source_msg"] = signal.key_quote
        if signal.category == "DISPUTE":
            memory["dispute_open"] = True
        update["memory"] = memory
    return update


def _stripe_status_to_payment_status(status: str) -> str:
    return "PAID" if status == "paid" else status.upper()


async def build_facts_node(state: InvoiceState, runtime: Runtime[GraphContext]) -> dict:
    context = runtime.context
    invoice = state["invoice"]
    client = state["client"]
    memory = state["memory"]
    signal = ResponseSignal.model_validate(state["signal"])

    count = memory.get("reminder_count", 0)
    reminder_timestamps = (
        [datetime.fromisoformat(memory["last_reminder_at"])] * count
        if memory.get("last_reminder_at") and count
        else []
    )

    facts = build_facts(
        invoice_id=invoice["id"],
        number=invoice["number"],
        client_id=client["client_id"],
        client_name=client["name"],
        client_tier=client["tier"],
        payment_status=_stripe_status_to_payment_status(invoice["status"]),
        amount_inr=invoice["amount"]["inr"],
        due_inr=invoice["due_amount"]["inr"],
        paid_inr=invoice["paid_amount"]["inr"],
        invoice_date=date.fromisoformat(invoice["invoice_date"]),
        due_date=date.fromisoformat(invoice["due_date"]),
        as_of=context.clock.now(),
        config=context.policy_config,
        reminder_timestamps=reminder_timestamps,
        last_client_msg_at=(
            datetime.fromisoformat(memory["last_client_msg_at"])
            if memory.get("last_client_msg_at")
            else None
        ),
        promise_date=date.fromisoformat(memory["promise_date"]) if memory.get("promise_date") else None,
        dispute_open=memory.get("dispute_open", False),
        refund_requested_inr=signal.refund_amount_inr,
        paused_until=date.fromisoformat(client["paused_until"]) if client.get("paused_until") else None,
        open_jira_key=memory.get("jira_key"),
        client_open_exposure_inr=state["client_open_exposure_inr"],
    )
    return {"facts": facts.model_dump(mode="json")}


async def score_node(state: InvoiceState, runtime: Runtime[GraphContext]) -> dict:
    facts = InvoiceFacts.model_validate(state["facts"])
    signal = ResponseSignal.model_validate(state["signal"])
    result = score_severity(facts, signal, runtime.context.policy_config)
    return {"severity": result.model_dump(mode="json")}


async def decide_node(state: InvoiceState, runtime: Runtime[GraphContext]) -> dict:
    facts = InvoiceFacts.model_validate(state["facts"])
    signal = ResponseSignal.model_validate(state["signal"])
    result = evaluate(facts, signal, runtime.context.policy_config)
    return {"decision": result.decision, "rule_id": result.rule_id, "reasons": [result.reason]}


async def counterfactuals_node(state: InvoiceState, runtime: Runtime[GraphContext]) -> dict:
    facts = InvoiceFacts.model_validate(state["facts"])
    signal = ResponseSignal.model_validate(state["signal"])
    hints = compute_counterfactuals(facts, signal, runtime.context.policy_config)
    return {"counterfactuals": hints}


async def plan_actions_node(state: InvoiceState, runtime: Runtime[GraphContext]) -> dict:
    context = runtime.context
    facts = InvoiceFacts.model_validate(state["facts"])
    signal = ResponseSignal.model_validate(state["signal"])
    actions = route(
        facts, signal, state["decision"], context.policy_config,
        flags=context.flags, demo_epoch=context.demo_epoch,
    )
    return {"plan": [a.model_dump(mode="json") for a in actions]}


def _tone_for(action_type: str, args_template: dict) -> str:
    return args_template.get("tone") or DEFAULT_TONE.get(action_type, "firm")


async def write_messages_node(state: InvoiceState, runtime: Runtime[GraphContext]) -> dict:
    context = runtime.context
    business = get_business_config()
    facts = InvoiceFacts.model_validate(state["facts"])
    signal = ResponseSignal.model_validate(state["signal"])
    invoice = state["invoice"]
    client = state["client"]
    amount_display = format_inr(facts.due_inr or facts.amount_inr)

    messages: dict = {}
    for action_dict in state["plan"]:
        action = PlannedAction.model_validate(action_dict)
        channel = MESSAGE_CHANNEL_BY_TOOL.get(action.tool_logical)
        if channel is None:
            continue
        brief = WriterBrief(
            channel=channel,
            decision=state["decision"],
            tone=_tone_for(action.action_type, action.args_template),
            client_name=client["name"],
            contact_name=client["contact_name"] or client["name"],
            invoice_number=invoice["number"],
            amount_display=amount_display,
            due_date=invoice["due_date"],
            days_overdue=facts.days_overdue,
            key_quote=signal.key_quote,
            promise_date=facts.promise_date.isoformat() if facts.promise_date else "",
            pay_link_note=(
                business.payment_link_note
                if action.action_type in ("gmail_reminder", "gmail_escalation")
                else ""
            ),
            business_name=business.business_name,
            tone_guide=business.tone_guide,
            signature=business.signature,
        )
        output = await write_message(brief, db=context.db, cache=context.llm_cache)
        messages[action.action_type] = output.model_dump(mode="json")
    return {"messages": messages}


RECIPIENT_BY_TOOL_KEY = {
    "gmail.send": "client_email",
    "twilio.sms.send": "owner_phone",
    "stripe.invoices.send": "client_email",
}


async def _notify_approval_needed(
    state: InvoiceState, action: PlannedAction, payload: dict | None, *, context: GraphContext
) -> None:
    """Posts a card to #munimji-approvals and remembers which message it is, so the
    Slack reaction poller (app/workers/slack_poller.py) knows where to watch for a
    ✅/❌ - it never blocks the sweep, the ledger entry already exists as pending_approval
    regardless of whether this notification succeeds."""
    invoice = state["invoice"]
    to = payload.get("to", "?") if payload else "?"
    subject = payload.get("subject", "") if payload else ""
    body_preview = (payload.get("body", "") if payload else "")[:300]
    text = (
        f":rotating_light: Approval needed - {invoice['number']} ({state['client']['name']}) - "
        f"{state['decision']}\n*To:* {to}"
        + (f"\n*Subject:* {subject}" if subject else "")
        + f"\n>{body_preview}\nReact :white_check_mark: to send, :x: to reject."
    )
    channel = workspace_ids()["slack"]["approvals_channel_id"]
    ctx = CallCtx(run_id=state["run_id"], invoice_id=invoice["id"], node="governance_gate")
    result = await slack.post(channel, text, ctx=ctx)
    if result.ok and result.data:
        await context.db.set_slack_ref(action.idem_key, channel=channel, message_ts=result.data["ts"])


async def governance_gate_node(state: InvoiceState, runtime: Runtime[GraphContext]) -> dict:
    from app.governance.gate import gate_action
    from app.settings import get_settings

    context = runtime.context
    now = context.clock.now().isoformat()
    settings = get_settings()
    recipients = {"client_email": state["client"]["email"], "owner_phone": settings.owner_phone_e164}

    results = []
    for action_dict in state["plan"]:
        action = PlannedAction.model_validate(action_dict)
        recipient_key = RECIPIENT_BY_TOOL_KEY.get(action.tool_logical)
        recipient = recipients.get(recipient_key) if recipient_key else None

        payload = None
        if action.tool_logical == "gmail.send":
            message = state["messages"].get(action.action_type)
            if message is not None:
                payload = {"to": recipient, "subject": message["subject"], "body": message["body"]}
        elif action.tool_logical == "twilio.sms.send":
            message = state["messages"].get(action.action_type)
            if message is not None:
                payload = {"to": recipient, "body": message["body"]}

        gate_result = await gate_action(
            action,
            ledger=context.ledger,
            allowlist=context.allowlist,
            run_id=state["run_id"],
            invoice_id=state["invoice"]["id"],
            dry_run_sends=context.dry_run_sends,
            now=now,
            recipient=recipient,
            payload=payload,
        )
        if gate_result.outcome == "approval_requested":
            await _notify_approval_needed(state, action, payload, context=context)
        results.append({"action": action.model_dump(mode="json"), "outcome": gate_result.outcome})
    return {"gate_results": results}


async def execute_node(state: InvoiceState, runtime: Runtime[GraphContext]) -> dict:
    context = runtime.context
    now = context.clock.now().isoformat()
    invoice = state["invoice"]

    results = []
    for gate_result in state["gate_results"]:
        action = PlannedAction.model_validate(gate_result["action"])
        outcome = gate_result["outcome"]
        entry = {
            "invoice_id": invoice["id"], "action_type": action.action_type,
            "tool": action.tool_logical, "outcome": outcome,
        }
        if outcome != "ready":
            results.append(entry)
            continue

        ctx = CallCtx(run_id=state["run_id"], invoice_id=invoice["id"], node="execute")
        await context.ledger.executing(action.idem_key, updated_at=now)
        tool_result = await execute_action(action, state, ctx=ctx, context=context)
        await context.db.insert_tool_call(
            run_id=state["run_id"], invoice_id=invoice["id"], node="execute",
            logical=action.tool_logical, canonical_id=tool_result.canonical_id,
            ok=tool_result.ok, policy_blocked=tool_result.policy_blocked,
            duration_ms=tool_result.duration_ms, ts=now,
        )
        if tool_result.ok:
            await context.ledger.done(action.idem_key, tool_result.data or {}, updated_at=now)
        else:
            await context.ledger.failed(action.idem_key, {"error": tool_result.error}, updated_at=now)

        entry["ok"] = tool_result.ok
        entry["error"] = tool_result.error
        if tool_result.ok and action.tool_logical == "jira.issue.create" and tool_result.data:
            entry["issue_key"] = tool_result.data.get("key")
        results.append(entry)
    return {"results": results}


def _advance_memory(state: InvoiceState) -> dict:
    memory = dict(state["memory"])
    facts = state["facts"]

    if any(r.get("ok") and r["action_type"] == "gmail_reminder" for r in state["results"]):
        memory["reminder_count"] = memory.get("reminder_count", 0) + 1
        memory["last_reminder_at"] = facts["as_of"]

    jira_created = next(
        (r for r in state["results"] if r.get("ok") and r["tool"] == "jira.issue.create"), None
    )
    if jira_created is not None:
        memory["jira_key"] = jira_created.get("issue_key", memory.get("jira_key"))

    memory["state"] = state_for_decision(state["decision"], facts["promise_status"])
    memory["last_decision"] = state["decision"]
    memory["last_severity"] = state["severity"]["score"]
    return memory


def _rt(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text[:2000]}}]}


async def _write_notion_decision_trace(
    state: InvoiceState, memory: dict, explanation: str, *, ctx: CallCtx
) -> None:
    """Mirrors the decision into Notion's Decision Traces db, alongside the SQLite copy
    insert_decision already wrote - the schema's been live since setup_notion.py, but
    nothing was ever filling it in, so the human-facing trace only existed in the API."""
    invoice = state["invoice"]
    properties = {
        "Name": {"title": [{"text": {"content": f"{invoice['number']} - {state['decision']}"}}]},
        "Run ID": _rt(state["run_id"]),
        "As Of": {"date": {"start": state["facts"]["as_of"]}},
        "Decision": {"select": {"name": state["decision"]}},
        "Rule ID": _rt(state["rule_id"]),
        "Severity": {"number": state["severity"]["score"]},
        "Facts": _rt(json.dumps(state["facts"])),
        "Client Signal": _rt(json.dumps(state["signal"])),
        "Reasons": _rt("; ".join(state["reasons"])),
        "Actions Taken": _rt(", ".join(r.get("action_type", "") for r in state["results"])),
        "Result": _rt(json.dumps(state["results"])),
        "Explanation": _rt(explanation),
    }
    if memory.get("notion_page_id"):
        properties["Invoice"] = {"relation": [{"id": memory["notion_page_id"]}]}

    decisions_db_id = workspace_ids()["notion"]["decisions_db_id"]
    await notion.create_page(decisions_db_id, properties, ctx=ctx)


async def _notify_client_replied(state: InvoiceState, *, ctx: CallCtx) -> None:
    """Posts a summary to #finance-ops the moment a client's reply is actually read and
    classified - the owner shouldn't have to open the dashboard just to find out someone
    said "I'll pay Friday" or "I already paid this". Fires once per genuinely new
    message: signal.category is only ever non-NO_RESPONSE when unseen_client_messages
    found something this run hadn't already advanced last_client_msg_at past (see
    interpret_node) - a re-read of an old, already-processed message reports
    NO_RESPONSE again, not a repeat of the old category."""
    signal = state["signal"]
    if signal["category"] == "NO_RESPONSE":
        return

    invoice = state["invoice"]
    lines = [
        f":speech_balloon: *{state['client']['name']}* replied on *{invoice['number']}* "
        f"— classified as `{signal['category']}`",
    ]
    if signal.get("key_quote"):
        lines.append(f'"{signal["key_quote"]}"')
    if signal.get("promise_date"):
        lines.append(f"Promised payment by {signal['promise_date']}.")
    if signal.get("claimed_reference"):
        lines.append(f"Claims paid, reference: {signal['claimed_reference']}.")
    lines.append(f"→ MunimJi's call: *{state['decision']}* (rule {state['rule_id']})")

    channel = workspace_ids()["slack"]["finance_ops_channel_id"]
    await slack.post(channel, "\n".join(lines), ctx=ctx)


async def record_trace_node(state: InvoiceState, runtime: Runtime[GraphContext]) -> dict:
    context = runtime.context
    now = context.clock.now().isoformat()
    invoice = state["invoice"]

    explanation = await explain_decision(
        state["decision"], state["rule_id"], state["reasons"], state["counterfactuals"],
        db=context.db, cache=context.llm_cache,
    )
    memory = _advance_memory(state)

    await context.db.upsert_invoice(
        invoice_id=invoice["id"], number=invoice["number"], client_id=state["client"]["client_id"],
        status=invoice["status"], amount_inr=invoice["amount"]["inr"], due_inr=invoice["due_amount"]["inr"],
        invoice_date=invoice["invoice_date"], due_date=invoice["due_date"],
        reminder_count=memory.get("reminder_count", 0), last_reminder_at=memory.get("last_reminder_at"),
        last_client_msg_at=memory.get("last_client_msg_at"), promise_date=memory.get("promise_date"),
        promise_source_msg=memory.get("promise_source_msg"), dispute_open=int(memory.get("dispute_open", False)),
        jira_key=memory.get("jira_key"), notion_page_id=memory.get("notion_page_id"),
        state=memory["state"], last_decision=memory["last_decision"], last_severity=memory["last_severity"],
        updated_at=now,
    )
    await context.db.insert_decision(
        run_id=state["run_id"], invoice_id=invoice["id"], as_of=now,
        facts_json=state["facts"], signal_json=state["signal"], severity=state["severity"]["score"],
        severity_breakdown_json=state["severity"]["breakdown"], decision=state["decision"],
        rule_id=state["rule_id"], reasons_json=state["reasons"],
        counterfactuals_json=state["counterfactuals"], plan_json=state["plan"],
        results_json=state["results"], explanation=explanation, created_at=now,
    )
    await context.bus.emit(
        state["run_id"], "invoice.decided", "record_trace",
        {
            "invoice_id": invoice["id"], "invoice_number": invoice["number"],
            "client_name": state["client"]["name"], "client_tier": state["client"]["tier"],
            "decision": state["decision"], "rule_id": state["rule_id"],
            "severity": state["severity"]["score"], "severity_band": state["severity"]["band"],
            "explanation": explanation, "reasons": state["reasons"],
            "counterfactuals": state["counterfactuals"],
            "amount_inr": state["facts"]["amount_inr"], "due_inr": state["facts"]["due_inr"],
            "days_overdue": state["facts"]["days_overdue"],
        },
        invoice_id=invoice["id"],
    )

    ctx = CallCtx(run_id=state["run_id"], invoice_id=invoice["id"], node="record_trace")
    try:
        await _write_notion_decision_trace(state, memory, explanation, ctx=ctx)
    except Exception:  # noqa: BLE001 - the trace is already safely in sqlite; a notion hiccup is not fatal
        pass
    try:
        await _notify_client_replied(state, ctx=ctx)
    except Exception:  # noqa: BLE001 - same: best-effort, never blocks or fails the sweep
        pass

    return {"explanation": explanation, "memory": memory}


def build_invoice_graph():
    graph = StateGraph(InvoiceState, context_schema=GraphContext)
    graph.add_node("read_thread", read_thread_node)
    graph.add_node("interpret", interpret_node)
    graph.add_node("build_facts", build_facts_node)
    graph.add_node("score", score_node)
    graph.add_node("decide", decide_node)
    graph.add_node("counterfactuals", counterfactuals_node)
    graph.add_node("plan_actions", plan_actions_node)
    graph.add_node("write_messages", write_messages_node)
    graph.add_node("governance_gate", governance_gate_node)
    graph.add_node("execute", execute_node)
    graph.add_node("record_trace", record_trace_node)

    graph.add_edge(START, "read_thread")
    graph.add_edge("read_thread", "interpret")
    graph.add_edge("interpret", "build_facts")
    graph.add_edge("build_facts", "score")
    graph.add_edge("score", "decide")
    graph.add_edge("decide", "counterfactuals")
    graph.add_edge("counterfactuals", "plan_actions")
    graph.add_edge("plan_actions", "write_messages")
    graph.add_edge("write_messages", "governance_gate")
    graph.add_edge("governance_gate", "execute")
    graph.add_edge("execute", "record_trace")
    graph.add_edge("record_trace", END)
    return graph.compile()


INVOICE_GRAPH = build_invoice_graph()
