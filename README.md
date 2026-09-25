# 🪔 MunimJi

> "Your AI munim who never sleeps, never forgets a payment, and knows exactly when to wait, when to nudge and when to call the boss."

An autonomous, governed **FinOps agent** that watches every payment, reads every client reply, decides what each situation deserves through a deterministic policy engine, and acts across PayPal, Gmail, Jira, Slack, Notion (+ Google Sheets, Twilio, Calendly) — all executed through **Swytchcode**.

Built for the Swytchcode Buildathon · Track 6 — AI Business Operator Agent.

Full spec: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Build rules for Claude Code: [CLAUDE.md](CLAUDE.md).

## Status

Work in progress, built phase by phase per the implementation plan. See commit history for progress.

## Architecture (short version)

- **Reasoning Layer (LLM)** — interprets client emails, writes messages, explains decisions. Never decides.
- **Policy Layer (deterministic Python)** — computes facts, severity, and the decision (`WAIT`, `FOLLOWUP`, `ESCALATE`, ...) from a fixed rule table.
- **Execution Layer (Swytchcode)** — the only path to PayPal, Gmail, Jira, Slack, Notion, Sheets, Twilio, Calendly. No provider SDKs anywhere in this repo.

Full diagram and request lifecycle in the implementation plan, Section 4.

## Setup

See the implementation plan, Section 7 (accounts) and Section 19 (build phases). Short version once phases are complete:

```bash
cp .env.example .env   # fill in credentials
make setup
make seed
make dev
```

## License

MIT
