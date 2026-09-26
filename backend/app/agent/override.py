"""Applies an owner override ("pause Bluepeak till Monday", "mark Zephyr VIP") straight
to Notion (the source of truth sense.py reads back next sweep) and mirrors it into the
local client cache. The policy layer still decides what a paused/re-tiered client means
(R05, tier_multipliers) - this only changes the facts it reads.
"""

from datetime import date

from app.agent import sense
from app.db import Database
from app.integrations import notion
from app.swy.executor import CallCtx

VALID_TIERS = {"VIP", "Regular", "New", "Watchlist"}


async def apply_override(args: dict, *, ctx: CallCtx, db: Database) -> str:
    client_query = (args.get("client") or "").strip()
    if not client_query:
        return "I couldn't tell which client this is about - please name them."

    clients = await sense.fetch_clients(ctx)
    match = next((c for c in clients if client_query.lower() in c.name.lower()), None)
    if match is None:
        return f"I couldn't find a client matching \"{client_query}\"."

    properties: dict = {}
    changes: list[str] = []

    paused_until_raw = args.get("paused_until")
    new_paused_until = match.paused_until
    if paused_until_raw:
        try:
            new_paused_until = date.fromisoformat(paused_until_raw)
        except ValueError:
            return f"\"{paused_until_raw}\" isn't a date I can parse (need YYYY-MM-DD)."
        properties["Paused Until"] = {"date": {"start": new_paused_until.isoformat()}}
        changes.append(f"paused reminders until {new_paused_until.isoformat()}")

    new_tier = match.tier
    tier_raw = args.get("tier")
    if tier_raw:
        tier_raw = tier_raw.strip().title() if tier_raw.lower() != "vip" else "VIP"
        if tier_raw not in VALID_TIERS:
            return f"\"{tier_raw}\" isn't a tier I know ({', '.join(sorted(VALID_TIERS))})."
        new_tier = tier_raw
        properties["Tier"] = {"select": {"name": new_tier}}
        changes.append(f"tier set to {new_tier}")

    if not properties:
        return f"I found {match.name} but didn't understand what to change."

    result = await notion.update_page(match.notion_page_id, properties, ctx=ctx)
    if not result.ok:
        return f"Found {match.name}, but the Notion update failed: {result.error}"

    await db.upsert_client(
        client_id=match.client_id,
        name=match.name,
        email=match.email,
        tier=new_tier,
        contact_name=match.contact_name,
        relationship_notes=match.relationship_notes,
        notion_page_id=match.notion_page_id,
        paused_until=new_paused_until.isoformat() if new_paused_until else None,
    )

    return f"Done - {match.name}: {', '.join(changes)}."
