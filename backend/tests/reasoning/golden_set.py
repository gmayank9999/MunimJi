"""30 labelled client messages for interpreter accuracy evaluation.

Mix of English and Hinglish, matching the tone of real client replies in this
domain. Each tuple is (message, expected_category, message_date).
"""

GOLDEN_SET: list[tuple[str, str, str]] = [
    ("Sir payment kal tak ho jayega.", "PROMISE_TO_PAY", "2026-09-24"),
    ("We will clear this by Friday for sure.", "PROMISE_TO_PAY", "2026-09-22"),
    ("Payment will be released by end of month.", "PROMISE_TO_PAY", "2026-09-10"),
    ("Finance team ne approve kar diya hai, next week tak ho jayega.", "PROMISE_TO_PAY", "2026-09-15"),
    ("We already transferred this on the 3rd, UTR 412398765012.", "CLAIMS_PAID", "2026-09-25"),
    ("This is already paid, please check your account.", "CLAIMS_PAID", "2026-09-20"),
    ("Humne toh pehle hi pay kar diya tha last week.", "CLAIMS_PAID", "2026-09-18"),
    ("Paid via bank transfer yesterday, screenshot attached.", "CLAIMS_PAID", "2026-09-25"),
    ("The website is still broken on mobile, will pay once fixed.", "DISPUTE", "2026-09-12"),
    ("We are not paying until the deliverable is corrected.", "DISPUTE", "2026-09-14"),
    ("Kaam abhi tak complete nahi hua hai, payment rok rahe hain.", "DISPUTE", "2026-09-16"),
    ("The design has bugs, we can't accept this as final.", "DISPUTE", "2026-09-11"),
    ("Noted, will check with accounts.", "ACKNOWLEDGED", "2026-09-19"),
    ("Thanks for the reminder, looking into it.", "ACKNOWLEDGED", "2026-09-20"),
    ("Ok, dekhte hain.", "ACKNOWLEDGED", "2026-09-21"),
    ("Received, will revert.", "ACKNOWLEDGED", "2026-09-22"),
    ("Can you give us two more weeks? Cash flow is tight.", "EXTENSION_REQUEST", "2026-09-13"),
    ("Please extend the deadline to next month, budget approval pending.", "EXTENSION_REQUEST", "2026-09-09"),
    ("Thoda time chahiye, next Monday tak extend kar sakte hain kya?", "EXTENSION_REQUEST", "2026-09-17"),
    ("We'd like this refunded, the banner work was cancelled.", "REFUND_REQUEST", "2026-09-10"),
    ("Please refund the advance we paid, we're not proceeding.", "REFUND_REQUEST", "2026-09-08"),
    ("Paisa wapas chahiye, hum ye project cancel kar rahe hain.", "REFUND_REQUEST", "2026-09-11"),
    ("This is ridiculous, stop harassing us with emails.", "HOSTILE", "2026-09-23"),
    ("Do not contact us again or we will report this to PayPal.", "HOSTILE", "2026-09-24"),
    ("Bas bahut ho gaya, roz roz mail mat karo.", "HOSTILE", "2026-09-22"),
    ("Can we get on a call sometime this week to discuss the project?", "OTHER", "2026-09-15"),
    ("What is the status of the next milestone?", "OTHER", "2026-09-16"),
    ("Please resend the invoice, I can't find the original.", "OTHER", "2026-09-14"),
    ("Congratulations on the new office launch!", "OTHER", "2026-09-05"),
    ("Hum agle hafte se project pe phir se kaam shuru karenge.", "OTHER", "2026-09-19"),
]
