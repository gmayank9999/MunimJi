# MunimJi decision table

Generated from `backend/app/policy/rules.py` and `backend/config/policy.yaml`. First match wins.

| # | Rule id | Condition | Decision |
|---|---|---|---|
| 01 | `R01` (paypal-dispute) | Open PayPal dispute on this invoice's payment | CRITICAL |
| 02 | `R02` (refund-request) | Client signal is REFUND_REQUEST | CRITICAL |
| 03 | `R03` (paid-close) | PayPal status is PAID/MARKED_AS_PAID, or due amount is zero | CLOSE |
| 04 | `R04` (refunded-close) | PayPal status is REFUNDED/MARKED_AS_REFUNDED | CLOSE |
| 05 | `R05` (owner-paused) | Owner paused reminders until a date on/after today | WAIT |
| 06 | `R06` (client-dispute) | Client signal is DISPUTE | DISPUTE_ROUTE |
| 07 | `R07` (claims-paid) | Client signal is CLAIMS_PAID and no PayPal payment on the invoice | RECONCILE |
| 08 | `R08` (claims-paid-verified) | Client signal is CLAIMS_PAID and PayPal shows a matching payment | CLOSE |
| 09 | `R09` (promise-pending) | Promise status is pending | WAIT |
| 10 | `R10` (promise-broken-big) | Promise status is broken and due amount >= escalate_amount_inr | ESCALATE |
| 11 | `R11` (promise-broken) | Promise status is broken | HIGH_PRIORITY |
| 12 | `R12` (extension-reasonable) | Client signal is EXTENSION_REQUEST, requested date <= 14 days past due, tier != Watchlist | WAIT |
| 13 | `R13` (max-reminders) | reminder_count >= max_reminders_before_human | HANDOVER |
| 14 | `R14` (not-due) | days_overdue == 0 | WAIT |
| 15 | `R15` (grace) | days_overdue <= grace_days | WAIT |
| 16 | `R16` (cooldown) | hours_since_last_reminder < reminder_cooldown_hours | WAIT |
| 17 | `R17` (critical-exposure) | days_overdue >= high_priority_after_days, due >= critical_amount_inr, signal is NO_RESPONSE/HOSTILE | CRITICAL |
| 18 | `R18` (escalate) | days_overdue >= high_priority_after_days, due >= escalate_amount_inr, unanswered >= min_reminders | ESCALATE |
| 19 | `R19` (high-priority) | days_overdue >= high_priority_after_days | HIGH_PRIORITY |
| 20 | `R20` (followup) | days_overdue >= followup_after_days | FOLLOWUP |
| 21 | `R21` (default-wait) | otherwise | WAIT |

## Thresholds

- Grace period: 2 day(s)
- Follow-up after: 3 day(s) overdue
- High priority after: 7 day(s) overdue
- Escalate threshold: ₹50,000
- Critical threshold: ₹1,50,000
- Reminder cooldown: 72h
- Max reminders before handover: 4
- Refund auto-propose max: ₹10,000
