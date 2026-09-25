# 🪔 MunimJi

> "Your AI munim who never sleeps, never forgets a payment, and knows exactly when to wait, when to nudge and when to call the boss."

An autonomous, governed **FinOps agent** that watches every payment, reads every client reply, decides what each situation deserves through a deterministic policy engine, and acts across PayPal, Gmail, Jira, Slack, Notion (+ Google Sheets, Twilio, Calendly) — all executed through **Swytchcode**.

Built for the Swytchcode Buildathon · Track 6 — AI Business Operator Agent.

Full spec: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Build rules for Claude Code: [CLAUDE.md](CLAUDE.md).

## Status

Work in progress, built phase by phase per the implementation plan. See commit history for progress.

- Policy Layer (facts, severity, all 21 rules, counterfactuals, router, decision table doc) — done, offline-tested.
- Reasoning Layer (interpreter, writer with template fallback, explainer, ask) — done, offline-tested.
- Governance (allowlist, ledger state machine, approval gate) — done, offline-tested.
- Backend API (health, kpis, policy, invoices, clients, runs, SSE event stream) — done.
- Frontend (Next.js + Tailwind, home/invoices/clients/policy/audit pages wired to the live API) — scaffolded.
- Swytchcode wiring (real PayPal/Gmail/Jira/Slack/Notion/Sheets/Twilio/Calendly) — blocked on `swy login` completing; see `CLAUDE.md` for the Swytchcode agent contract.
- LangGraph agent orchestration, workers, MunimJi Lens extension — not started yet.

### Deviations from the plan

- **LLM provider**: the plan specifies Anthropic (`claude-sonnet-5` / `claude-haiku-4-5`). This build uses **Groq's free tier** (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`) instead — set `GROQ_API_KEY` in `.env`, not `ANTHROPIC_API_KEY`.

## Architecture (short version)

- **Reasoning Layer (LLM)** — interprets client emails, writes messages, explains decisions. Never decides.
- **Policy Layer (deterministic Python)** — computes facts, severity, and the decision (`WAIT`, `FOLLOWUP`, `ESCALATE`, ...) from a fixed rule table.
- **Execution Layer (Swytchcode)** — the only path to PayPal, Gmail, Jira, Slack, Notion, Sheets, Twilio, Calendly. No provider SDKs anywhere in this repo.

Full diagram and request lifecycle in the implementation plan, Section 4.

## Setup

See the implementation plan, Section 7 (accounts) and Section 19 (build phases). Short version once phases are complete:

```bash
cp .env.example .env   # fill in credentials (GROQ_API_KEY, not ANTHROPIC_API_KEY)
make setup
make seed
make dev
```

### Running today (backend + frontend only, no live integrations yet)

```bash
# backend
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt -r requirements-dev.txt
.venv/Scripts/uvicorn app.main:app --reload --port 8000

# frontend, in a second terminal
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

## License

MIT
