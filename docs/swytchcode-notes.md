# Swytchcode integration notes

Recorded 2026-09-25 while wiring Phase 1. Trust this over IMPLEMENTATION_PLAN.md Section 8 wherever they
differ — everything here was verified against the live registry with `swy info` and real `swy exec` calls
(not just `--dry-run` - see why below).

## `--mode sandbox` routes everything to localhost - use `--mode production`

`swy init` was originally run with `--mode sandbox` (Phase 1), on the assumption "sandbox" meant "use each
provider's own test/sandbox environment" (Stripe test mode, etc.). **It does not.** In this Swytchcode
version, project mode `sandbox` hard-codes every provider's endpoint to `http://localhost` regardless of
which method is called - confirmed by inspecting `.swytchcode/integrations/manifest.json`, where every
provider entry has `"sandbox_endpoint": "http://localhost"` alongside its real `"production_endpoint"`.
**This affected `--dry-run` previews too**, which is why they kept looking fine (`"url":
"http://localhost/v2/invoicing/invoices..."` was treated as a successful preview) while every real
(non-dry-run) call failed with `category: "network"` ("connection refused" - nothing listens on
`localhost:80`). Dry-run success is a weak signal; the smoke script now uses real calls for exactly this
reason.

Fixed by re-running `swy init --mode production --editor claude --non-interactive` in the project root
(non-destructive - just flips `"mode"` in `.swytchcode/tooling.json` from `"sandbox"` to `"production"`).
"Production" here only means "call the real API endpoint" - it says nothing about test vs. live credentials,
which is controlled entirely by which key/account you connected (our Stripe key is `sk_test_...`, so this is
still safe test-mode data). After the switch, `swy exec <id> --dry-run` correctly previews
`https://api.stripe.com/...` etc., and real calls succeed. **One side effect**: the Jira OAuth connection
made while in sandbox mode stopped working (`401 authorization failed ... the connection may be revoked`)
and had to be reconnected with `swy auth connect Jira` again after the mode switch; the other
Swytchcode-managed OAuth connections (Gmail, Slack, Notion) survived the switch fine.

## Connection status (real API calls confirmed, not just dry-run)

| Provider | Status | Auth type |
|---|---|---|
| Stripe | connected, confirmed live (`GET https://api.stripe.com/v1/invoices` -> 200) | `api_key` |
| Gmail | connected, confirmed live (real labels returned) | `oauth2` (Swytchcode-managed) |
| Notion | connected, confirmed live (found the real "MunimJi HQ" page) | `oauth2` (Swytchcode-managed) |
| Slack | connected, confirmed live (real workspace channels returned) | `oauth2` (Swytchcode-managed) |
| Jira | connected, needed a reconnect after the mode switch | `oauth2` (Swytchcode-managed) |
| Twilio | connected (not exercised for real - `sms_owner` stays dry-run in the smoke script so it never sends an actual SMS) | `api_key`-style (needs explicit `AccountSid`, see below) |
| Google Sheets | not connected | custom/BYO OAuth app required, deferred - it's an extra, not a required track integration |
| Calendly | unavailable | registry bundle is broken (see below) |

`make smoke` (`scripts/smoke_swytchcode.py`) exercises one **real** read per integration (Twilio stays
dry-run) plus the `block-invoice-void` policy check and prints a pass/fail table.

## PayPal was replaced with Stripe

PayPal is one of the plan's 5 required track integrations, but `swy auth connect PayPal` is broken on
Swytchcode's side: it opens a browser OAuth flow through Swytchcode's own auth broker
(`auth.swytchcode.com`), which redirects to PayPal's OAuth authorize endpoint using a **Swytchcode-owned**
client_id (not the user's own sandbox app credentials) - and PayPal rejects it outright ("invalid client_id
or redirect_uri"). This isn't fixable from the user's PayPal sandbox app settings, since the rejected
client_id belongs to Swytchcode, not the user. A Swytchcode team member confirmed PayPal requires a paid
plan tier; Stripe (auth type `api_key`, a pasted secret key, no OAuth broker involved) works cleanly and was
adopted as the payments/invoicing integration instead. Every "PayPal invoice" reference in
IMPLEMENTATION_PLAN.md should be read as "Stripe invoice" - the product concept (list/get/send/void invoices,
list disputes, refund charges) carries over unchanged, only the concrete API differs.

### Verified Stripe canonical IDs

See `backend/config/tool_registry.yaml` for the authoritative mapping. Stripe's invoice lifecycle splits
into more distinct calls than PayPal's:

| Logical name | Canonical ID | Notes |
|---|---|---|
| `stripe.invoices.list` | `stripe.invoice.list` | `GET /v1/invoices` |
| `stripe.invoices.get` | `stripe.invoice.get` | `GET /v1/invoices/{invoice}` |
| `stripe.invoices.create` | `stripe.invoice.create` | draft only; setup-only |
| `stripe.invoices.finalize` | `stripe.finalize.create` | draft -> finalized; setup-only |
| `stripe.invoices.send` | `stripe.send.create` | also used to **re-send/nudge** - Stripe has no separate "remind" endpoint |
| `stripe.invoices.pay` | `stripe.pay.create` | manual payment attempt; setup-only, used by `simulate_payment.py` |
| `stripe.invoices.void` | `stripe.void.create1` | **blocked** - `stripe.void.create` (no suffix) is unrelated (credit-note void) |
| `stripe.disputes.list` | `stripe.dispute.list` | `GET /v1/disputes`; `dispute.get1` is get-by-id if needed later |
| `stripe.charges.refund` | `stripe.refund.create3` | `POST /v1/charges/{charge}/refund`; there are 8 numbered `refund.create*` variants, this is "Create a refund" |

Amounts are integers in the smallest currency unit (cents), not decimal strings like PayPal -
`app/integrations/stripe.py`'s `_cents_to_money` divides by 100 before building a `Money`.

## Other verified canonical IDs (unchanged providers)

- Gmail's `messages.get` (no suffix) is actually **list messages**; `messages.get1` is **get one message**.
  Same pattern for `threads` and `labels`. `send.create` sends an existing **draft**; `send.create1` sends a
  message directly - we want `send.create1`.
- Jira's classic JQL search endpoints (`search.list7` GET, `search.create1` POST) are both marked
  "Currently being removed" by Atlassian. Use the new one instead: `jira.api.jql.create`
  (POST /rest/api/3/search/jql).
- Jira's `jira.api.issue.delete` is NOT issue deletion (it's "Replace custom field options", despite the
  name). The real single-issue delete is `jira.api.issue.delete2`.
- Notion's current API (`Notion.notion@2.0.0`) uses "data source" instead of "database" as the schema-bearing
  object (`notion.data_source.create`, `notion.query.create`). `notion.blocks.append` is
  `notion.children.update` (Notion's own API expresses "append children" as a PATCH/update).
- Twilio SMS is `twilio.2010-04-01.messages.create` under `Twilio.twilio_api_v2010@2010-04-01` (disambiguate
  explicitly - the same id also exists, wrongly, under a `Twilio.twilio@1.0.0` bundle).

## Twilio needs an explicit AccountSid

Even with Twilio connected (`swy auth connect Twilio`), `twilio.2010-04-01.messages.create` requires
`AccountSid` as an explicit path param - it is not auto-filled from the connected credentials the way
`Authorization` is. Confirmed live: omitting it fails with `input validation failed: missing required field
"AccountSid"`. `app/integrations/twilio.py` takes it from `TWILIO_ACCOUNT_SID` in `.env` (visible, non-secret,
on the Twilio Console dashboard) by default.

## Google Sheets needs a custom OAuth app

Unlike Gmail/Jira/Slack/Notion (Swytchcode has a shared managed OAuth app for those), `swy auth connect
"Google Sheets"` prompts for a self-registered OAuth app (Client ID/Secret/Authorization URL/Token URL) -
Swytchcode has no managed Google Sheets app. This means a Google Cloud Console project + enabled Sheets API +
OAuth client is needed, and the exact redirect URI Swytchcode expects isn't documented anywhere we could
find (checked `/cli/authentication/`, `/guides/managed-authentication/`, `/cli/integrations/`; none list it,
and the connection page itself doesn't display one). Deferred since Sheets is an extra, not a required track
integration; `FEATURE_SHEETS=false` until this is set up. If revisited, ask Swytchcode support/Discord for
the exact redirect URI before spending time in Google Cloud Console.

## Calendly is unavailable

The only Calendly bundle in the registry (`Calendly.calendly@2.0.0`) is mislabeled: both of its 2 methods
(`admin_payments_payment_transactions.payment.authorizations.create` /
`...purchases.create`) are actually a BigCommerce-style payments API
(`POST /stores/{store_hash}/v3/payments/transactions/authorizations`), not Calendly's scheduling API. This
reproduced after a forced re-fetch (`swy get calendly --yes`), so it's not a transient fetch glitch.

`FEATURE_CALENDLY` defaults to `false` until Swytchcode fixes this bundle. The ESCALATE action plan skips
the scheduling-link step when the flag is off; everything else in the demo works without it.

## Policy engine (v1) constraints

- **Dotted field paths are not supported.** `swy policy add --field body.amount.value` saves without error
  but `swy policy validate` then fails with `field "..." uses a dotted path - dotted paths are not supported
  in v1, use a flat field name`. Only top-level input names can be guarded (e.g. `invoice`, `id`, `body`
  as a whole via `exists`). This means an amount-conditional block (the plan's `block-large-refund`, "> ₹10,000")
  **cannot be expressed as a Swytchcode policy today.** The ₹10,000 auto-propose threshold is enforced purely
  in MunimJi's own Policy Layer (`config/policy.yaml` `refund_auto_propose_max_inr`, `policy/router.py`):
  the router simply never plans a `stripe_refund` action above the threshold in the normal flow.
- **REQUIRES_APPROVAL is not usable on this Swytchcode plan.** A policy with `action: REQUIRES_APPROVAL`
  saves and validates fine, but every real `swy exec` against it fails with `approval requests are not
  included in your current plan - upgrade at https://app.swytchcode.com/dashboard/payments/plans`. So
  Swytchcode's native approval flow is out; MunimJi's own Governance Gate (`governance/gate.py` +
  `governance/ledger.py`, `pending_approval` -> Slack ✅/❌ or UI) is the **only** approval mechanism, exactly
  as Section 8.6's "two-layer governance" fallback anticipated.
- **POLICY_BLOCKED works exactly as documented.** Confirmed live via dry-run:
  ```
  swy exec stripe.void.create1 --input invoice=in_test123 --dry-run --json
  -> exit code 6, category "policy_denied"
  -> {"error":"blocked by policy \"block-invoice-void\": Voiding invoices (write-offs) must be done by the owner.", ...}
  ```
  `executor.py` classifies any error with `category == "policy_denied"` as `policy_blocked = True` and reads
  the policy id out of the `error` string (`blocked by policy "<id>": <message>`).
- Active policies today: `block-invoice-void`, `block-gmail-delete`, `block-jira-delete` (all
  `field: <id-like-field> exists` -> `POLICY_BLOCKED`; confirmed firing live for all three). `swy policy
  validate` prints a spurious warning about `block-jira-delete`'s field not matching the tool's inputs even
  though the field name is correct and the policy fires correctly live - a validator false positive, not a
  real problem. No SMS-recipient policy yet - it needs `OWNER_PHONE_E164` (now in `.env`); add it with:
  ```
  swy policy add --non-interactive --id sms-to-owner-only --target twilio.2010-04-01.messages.create \
    --field To --operator == --value "+918053867134" --action POLICY_BLOCKED \
    --message "MunimJi may only text the business owner."
  ```
  (Layer 2's `governance/allowlist.py` already enforces this regardless.)

## Error shape (`swy exec --json` on failure)

```json
{
  "error": "human readable message",
  "category": "auth | policy_denied | policy_error | validation | not_found | network | rate_limit | internal",
  "suggested_action": "...",
  "docs_url": "https://docs.swytchcode.com/...",
  "reference_id": "SWY-ERR-XXXXXX"   // present on some errors, useful for Swytchcode support
}
```
Exit codes observed: `3` = auth (missing credentials), `6` = policy_denied, policy_error, or validation
failure, `7` = approval required (dry-run only; real execs fail with 6 on this plan, see above).

## Campus network flakiness

Connectivity to `api-v2.swytchcode.com` (login, `auth connect`, `get`) was intermittently unreachable
(`context deadline exceeded`) throughout setup, while `swytchcode.com` and other sites worked fine - traced
to the dev machine's network (resolves DNS through a `bmu.edu.in` campus server). Dry-run/policy-only work
(no live API calls) was unaffected. If `auth connect` or `get` times out, just retry - it's not a code issue.
