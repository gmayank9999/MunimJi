"""The top-level sweep graph: sense (load real Stripe/Notion state) -> fan out one
Send per invoice to the compiled per-invoice sub-graph (see invoice_graph.py) ->
summarize. Checkpointed so a crashed sweep can resume instead of re-running invoices
that already finished (see run_sweep, the actual entry point - the module-level
compiled graph has no checkpointer and is for introspection/tests only)."""

from contextlib import asynccontextmanager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Send

from app.agent import sense
from app.agent import summary as summary_module
from app.agent.context import GraphContext
from app.agent.invoice_graph import INVOICE_GRAPH
from app.agent.schemas import InvoiceContext
from app.agent.state import InvoiceState, RunState
from app.swy.executor import CallCtx


def _matches_scope(context: InvoiceContext, scope: str) -> bool:
    if scope.startswith("client:"):
        name = scope.split(":", 1)[1].strip().lower()
        return name in context.client.name.lower()
    if scope.startswith("invoice:"):
        number = scope.split(":", 1)[1].strip()
        return context.invoice.number == number
    return context.invoice.due_amount.inr > 0 or context.memory.dispute_open  # "all_open"


async def sense_node(state: RunState, runtime: Runtime[GraphContext]) -> dict:
    context = runtime.context
    await context.bus.emit(state["run_id"], "run.sensing", "sense", {})
    ctx = CallCtx(run_id=state["run_id"], node="sense")
    contexts = await sense.build_invoice_contexts(ctx, context.db)
    scope = (state.get("intent_args") or {}).get("scope", "all_open")
    selected = [c for c in contexts if _matches_scope(c, scope)]
    await context.bus.emit(
        state["run_id"], "run.sensed", "sense",
        {"invoices_found": len(contexts), "invoices_in_scope": len(selected), "scope": scope},
    )
    return {"invoices": [c.model_dump(mode="json") for c in selected]}


def fan_out(state: RunState):
    if not state["invoices"]:
        return "summarize"
    return [
        Send(
            "process_invoice",
            {
                "run_id": state["run_id"],
                "invoice": ctx["invoice"],
                "client": ctx["client"],
                "memory": ctx["memory"],
                "dispute": ctx["dispute"],
                "client_open_exposure_inr": ctx["client_open_exposure_inr"],
            },
        )
        for ctx in state["invoices"]
    ]


async def process_invoice_node(state: InvoiceState, runtime: Runtime[GraphContext]) -> dict:
    result_state = await INVOICE_GRAPH.ainvoke(state, context=runtime.context)
    return {
        "results": [
            {
                "invoice_id": result_state["invoice"]["id"],
                "invoice_number": result_state["invoice"]["number"],
                "client_name": result_state["client"]["name"],
                "decision": result_state["decision"],
                "rule_id": result_state["rule_id"],
                "severity": result_state["severity"]["score"],
                "explanation": result_state["explanation"],
            }
        ]
    }


async def summarize_node(state: RunState, runtime: Runtime[GraphContext]) -> dict:
    context = runtime.context
    results = state.get("results", [])
    counts: dict[str, int] = {}
    exposure_inr = 0
    for r in results:
        counts[r["decision"]] = counts.get(r["decision"], 0) + 1
    for invoice_dict in state.get("invoices", []):
        exposure_inr += invoice_dict["invoice"]["due_amount"]["inr"]

    run_id = state["run_id"]
    summary = {
        "invoices_scanned": len(state.get("invoices", [])),
        "counts_per_decision": counts,
        "exposure_inr": exposure_inr,
        "swytchcode_calls": await context.db.count_tool_calls_for_run(run_id),
        "policy_blocks": await context.db.count_policy_blocks_for_run(run_id),
        "approvals_pending": await context.db.count_pending_approvals_for_run(run_id),
        "results": results,
    }
    now = context.clock.now().isoformat()
    await context.db.finish_run(run_id, now, summary)
    await context.bus.emit(run_id, "run.finished", "summarize", summary)

    run_row = await context.db.get_run(run_id)
    if run_row is not None:
        ctx = CallCtx(run_id=run_id, node="summarize")
        for coro in (
            summary_module.post_slack_digest(summary, run_id=run_id, prompt=run_row["prompt"], ctx=ctx),
            summary_module.write_run_report(
                summary, run_id=run_id, prompt=run_row["prompt"], started_at=run_row["started_at"], ctx=ctx
            ),
        ):
            try:
                result = await coro
                await context.db.insert_tool_call(
                    run_id=run_id, invoice_id=None, node="summarize", logical=result.logical,
                    canonical_id=result.canonical_id, ok=result.ok, policy_blocked=result.policy_blocked,
                    duration_ms=result.duration_ms, ts=now,
                )
            except Exception:  # noqa: BLE001 - the sweep already finished; a reporting hiccup is not the sweep's failure
                pass

    return {"summary": summary}


def build_run_graph(*, checkpointer=None):
    graph = StateGraph(RunState, context_schema=GraphContext)
    graph.add_node("sense", sense_node)
    graph.add_node("process_invoice", process_invoice_node, input_schema=InvoiceState)
    graph.add_node("summarize", summarize_node)

    graph.add_edge(START, "sense")
    graph.add_conditional_edges("sense", fan_out, ["process_invoice", "summarize"])
    graph.add_edge("process_invoice", "summarize")
    graph.add_edge("summarize", END)
    return graph.compile(checkpointer=checkpointer)


RUN_GRAPH = build_run_graph()


@asynccontextmanager
async def checkpointed_run_graph(checkpoint_db_path: str):
    async with AsyncSqliteSaver.from_conn_string(checkpoint_db_path) as saver:
        yield build_run_graph(checkpointer=saver)


async def run_sweep(
    *,
    run_id: str,
    context: GraphContext,
    intent_args: dict | None = None,
    checkpoint_db_path: str,
) -> RunState:
    """The real entry point (checkpointed - a crashed sweep resumes from its last
    completed invoice on the next call with the same run_id)."""
    initial_state: RunState = {
        "run_id": run_id, "source": "ui", "intent_args": intent_args or {},
    }
    config = {"configurable": {"thread_id": run_id}}
    async with checkpointed_run_graph(checkpoint_db_path) as graph:
        return await graph.ainvoke(initial_state, context=context, config=config)
