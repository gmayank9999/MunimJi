"""One-off fix: the demo's client emails were kaarigar.clients.sim+<name>@gmail.com,
assuming that base inbox existed - it doesn't, so every reminder bounced. Switches all 8
clients to real plus-addresses of an inbox the user actually owns, updates the already-
seeded Stripe customers (email + a munimji_client_id metadata stamp, so sense.py's
invoice->client matching never depends on email again) and Notion client pages to match.

Run from backend/: python scripts/fix_client_emails.py (after updating seed/clients.yaml
and config/allowlist.yaml with the new address pattern).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from app.integrations import notion, stripe  # noqa: E402
from app.swy.executor import CallCtx  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
CLIENTS_PATH = BACKEND_DIR / "seed" / "clients.yaml"
SEEDED_IDS_PATH = BACKEND_DIR / "seed" / "seeded_ids.yaml"


async def main() -> None:
    ctx = CallCtx(run_id="fix_emails", node="fix_client_emails")
    clients = yaml.safe_load(CLIENTS_PATH.read_text(encoding="utf-8"))
    seeded = yaml.safe_load(SEEDED_IDS_PATH.read_text(encoding="utf-8"))
    customer_ids = seeded["customers"]
    client_pages = seeded["notion_client_pages"]

    for client in clients:
        client_id = client["client_id"]
        new_email = client["email"]
        customer_id = customer_ids[client_id]

        result = await stripe.update_customer(
            customer_id, email=new_email, metadata={"munimji_client_id": client_id}, ctx=ctx
        )
        if not result.ok:
            raise RuntimeError(f"failed to update stripe customer {customer_id} ({client_id}): {result.error}")
        print(f"stripe {client_id} ({customer_id}): email -> {new_email}, metadata.munimji_client_id set")

        page_id = client_pages[client_id]
        result = await notion.update_page(page_id, {"Email": {"email": new_email}}, ctx=ctx)
        if not result.ok:
            raise RuntimeError(f"failed to update notion client page {page_id} ({client_id}): {result.error}")
        print(f"notion {client_id} ({page_id}): email -> {new_email}")


if __name__ == "__main__":
    asyncio.run(main())
