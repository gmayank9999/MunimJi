import pytest

from app.agent import override
from app.agent.schemas import Client
from app.db import Database
from app.swy.executor import CallCtx, ToolCallResult

CTX = CallCtx(run_id="test", node="override")


def _client(**overrides) -> Client:
    base = dict(
        client_id="C02", name="Bluepeak Media", email="mayankguptawp+bluepeak@gmail.com",
        tier="Regular", contact_name="Neha Arora", relationship_notes="", notion_page_id="page123",
        paused_until=None,
    )
    base.update(overrides)
    return Client(**base)


def _fetch_clients_returning(clients: list[Client]):
    async def _fake(ctx):
        return clients

    return _fake


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "override.db"))
    await database.connect()
    yield database
    await database.close()


async def test_no_client_named_asks_for_one(db):
    result = await override.apply_override({}, ctx=CTX, db=db)
    assert "couldn't tell" in result


async def test_unknown_client_reports_not_found(db, monkeypatch):
    monkeypatch.setattr(override.sense, "fetch_clients", _fetch_clients_returning([]))
    result = await override.apply_override({"client": "Nobody Inc"}, ctx=CTX, db=db)
    assert "couldn't find" in result


async def test_bad_date_format_is_rejected(db, monkeypatch):
    monkeypatch.setattr(override.sense, "fetch_clients", _fetch_clients_returning([_client()]))
    result = await override.apply_override(
        {"client": "Bluepeak", "paused_until": "next monday"}, ctx=CTX, db=db
    )
    assert "isn't a date" in result


async def test_unknown_tier_is_rejected(db, monkeypatch):
    monkeypatch.setattr(override.sense, "fetch_clients", _fetch_clients_returning([_client()]))
    result = await override.apply_override({"client": "Bluepeak", "tier": "Platinum"}, ctx=CTX, db=db)
    assert "isn't a tier" in result


async def test_no_recognized_field_asks_what_to_change(db, monkeypatch):
    monkeypatch.setattr(override.sense, "fetch_clients", _fetch_clients_returning([_client()]))
    result = await override.apply_override({"client": "Bluepeak"}, ctx=CTX, db=db)
    assert "didn't understand" in result


async def test_full_iso_datetime_paused_until_is_accepted(db, monkeypatch):
    """The supervisor LLM sometimes returns a full datetime instead of a plain date -
    must not be rejected as unparseable."""
    monkeypatch.setattr(override.sense, "fetch_clients", _fetch_clients_returning([_client()]))

    async def fake_update_page(page_id, properties, *, ctx):
        return ToolCallResult(logical="notion.page.update", canonical_id="x", ok=True, duration_ms=1)

    monkeypatch.setattr(override.notion, "update_page", fake_update_page)

    result = await override.apply_override(
        {"client": "Bluepeak", "paused_until": "2026-09-29T00:00:00+05:30"}, ctx=CTX, db=db
    )
    assert "paused reminders until 2026-09-29" in result


async def test_successful_pause_updates_notion_and_local_db(db, monkeypatch):
    monkeypatch.setattr(override.sense, "fetch_clients", _fetch_clients_returning([_client()]))

    captured = {}

    async def fake_update_page(page_id, properties, *, ctx):
        captured["page_id"] = page_id
        captured["properties"] = properties
        return ToolCallResult(logical="notion.page.update", canonical_id="x", ok=True, duration_ms=1)

    monkeypatch.setattr(override.notion, "update_page", fake_update_page)

    result = await override.apply_override(
        {"client": "Bluepeak", "paused_until": "2026-09-29"}, ctx=CTX, db=db
    )

    assert "paused reminders until 2026-09-29" in result
    assert captured["page_id"] == "page123"
    assert captured["properties"]["Paused Until"]["date"]["start"] == "2026-09-29"

    row = await db.get_client("C02")
    assert row["paused_until"] == "2026-09-29"


async def test_notion_failure_is_reported_not_crashed(db, monkeypatch):
    monkeypatch.setattr(override.sense, "fetch_clients", _fetch_clients_returning([_client()]))

    async def fake_update_page(page_id, properties, *, ctx):
        return ToolCallResult(
            logical="notion.page.update", canonical_id="x", ok=False, error="boom", duration_ms=1
        )

    monkeypatch.setattr(override.notion, "update_page", fake_update_page)

    result = await override.apply_override({"client": "Bluepeak", "tier": "VIP"}, ctx=CTX, db=db)
    assert "Notion update failed" in result
