# Swytchcode integration notes

Recorded 2026-09-25 while wiring Phase 1. Trust this over IMPLEMENTATION_PLAN.md Section 8 wherever they
differ — everything here was verified against the live registry with `swy info` / `swy exec --dry-run`.

## Verified canonical IDs

See `backend/config/tool_registry.yaml` for the authoritative mapping (logical name -> verified id).
Highlights of where the real API differs from the plan's candidate IDs:

- PayPal invoice search is `invoices.invoicing.searchInvoices.create` (POST), not a `search-invoices` id.
- PayPal refund is `payments.payment.captures.refund` under `PayPal.payments_payment_v2@2.0` (there's a
  second, legacy copy under `PayPal.paypal_api@1.0.0` - don't use that one, always disambiguate with
  `swy add method PayPal@payments_payment_v2.2.0 payments.payment.captures.refund`).
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

## PayPal `swy auth connect` is broken (Swytchcode-side, not user-side)

`swy auth connect PayPal` opens a browser OAuth flow through Swytchcode's own auth broker
(`auth.swytchcode.com`), which redirects to PayPal's OAuth authorize endpoint using a **Swytchcode-owned**
client_id (not the user's own sandbox REST app's Client ID/Secret). PayPal rejects it outright:

> Sorry about that... like this action is not supported... (invalid client_id or redirect_uri)

This is not fixable from the user's PayPal sandbox app settings, since the rejected client_id belongs to
Swytchcode, not to the user's app. `swy info` on every PayPal method also shows no `Auth:` metadata block
(unlike Jira, which shows `{"provider_slug": "Jira", "scopes": [], "type": "oauth2"}`), suggesting PayPal's
auth metadata is incomplete/misconfigured in the registry - consistent with the connect flow being broken.
`swy doctor` shows no other issues (bundles parse fine, session valid). This looks like a genuine bug on
Swytchcode's side worth reporting to their support, since PayPal is one of the 5 required track
integrations. Revisit `swy auth connect PayPal` periodically in case it's fixed upstream; PayPal dry-run
calls (no live data) and policy enforcement (`block-invoice-cancel`) both work fine without credentials, so
executor/registry/policy work isn't blocked - only real PayPal API calls are.

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
  in v1, use a flat field name`. Only top-level input names can be guarded (e.g. `invoice_id`, `id`, `body`
  as a whole via `exists`). This means an amount-conditional block (the plan's `block-large-refund`, "> ₹10,000")
  **cannot be expressed as a Swytchcode policy today.** The ₹10,000 auto-propose threshold is enforced purely
  in MunimJi's own Policy Layer (`config/policy.yaml` `refund_auto_propose_max_inr`, `policy/router.py`):
  the router simply never plans a `paypal_refund` action above the threshold in the normal flow.
- **REQUIRES_APPROVAL is not usable on this Swytchcode plan.** A policy with `action: REQUIRES_APPROVAL`
  saves and validates fine, but every real `swy exec` against it fails with `approval requests are not
  included in your current plan - upgrade at https://app.swytchcode.com/dashboard/payments/plans`. So
  Swytchcode's native approval flow is out; MunimJi's own Governance Gate (`governance/gate.py` +
  `governance/ledger.py`, `pending_approval` -> Slack ✅/❌ or UI) is the **only** approval mechanism, exactly
  as Section 8.6's "two-layer governance" fallback anticipated. `approve-refund` was removed from
  `.swytchcode/integrations/policies.json` for this reason.
- **POLICY_BLOCKED works exactly as documented.** Confirmed live via dry-run:
  ```
  swy exec invoices.invoicing.invoices.cancel --input invoice_id=INV2-TEST --dry-run --json
  -> exit code 6, category "policy_denied"
  -> {"error":"blocked by policy \"block-invoice-cancel\": Cancelling invoices (write-offs) must be done by the owner.", ...}
  ```
  `executor.py` classifies any error with `category == "policy_denied"` as `policy_blocked = True` and reads
  the policy id out of the `error` string (`blocked by policy "<id>": <message>`).
- Active policies today: `block-invoice-cancel`, `block-gmail-delete`, `block-jira-delete` (all
  `field: <id-like-field> exists` -> `POLICY_BLOCKED`). No SMS-recipient policy yet - it needs the real
  `OWNER_PHONE_E164` value, which only exists once `.env` is filled in; add it with:
  ```
  swy policy add --non-interactive --id sms-to-owner-only --target twilio.2010-04-01.messages.create \
    --field To --operator == --value "<OWNER_PHONE_E164>" --action POLICY_BLOCKED \
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
Exit codes observed: `3` = auth (missing credentials), `6` = policy_denied or policy_error, `7` = approval
required (dry-run only; real execs fail with 6 on this plan, see above).

## Auth ordering

For PayPal, `--dry-run` reaches policy evaluation even with no credentials connected. For Gmail and Jira
(OAuth-based), `--dry-run` fails fast with `category: "auth"` ("missing credentials ... run `swy auth connect
<Provider>`") before policy evaluation is reached. Don't rely on ordering between auth and policy checks -
`executor.py` only inspects the `category` field.

## Still to do once provider accounts exist

Run `swy auth connect <provider>` for each of PayPal, Gmail, Jira, Slack, Notion, Google Sheets, Twilio
(Calendly skipped, see above) once sandbox/dev accounts are created (Section 7). Re-run
`scripts/smoke_swytchcode.py` after each connection.
