from datetime import date

from app.agent.schemas import Client
from app.swy.executor import CallCtx, ToolCallResult, call


def _plain_text(rich_text: list[dict]) -> str:
    return "".join(fragment["plain_text"] for fragment in rich_text)


async def update_database_schema(
    data_source_id: str,
    properties: dict,
    *,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    """Add/modify a data source's properties (columns). Swytchcode's Notion bundle has
    no database-creation endpoint (see docs/swytchcode-notes.md) - databases are created
    by hand in the UI, then this adds their schema."""
    body = {"properties": properties}
    return await call(
        "notion.db.update_schema",
        {"params": {"data_source_id": data_source_id}, "body": body},
        ctx=ctx,
        dry_run=dry_run,
    )


async def query_database(
    data_source_id: str,
    *,
    filter: dict | None = None,
    page_size: int = 100,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    body: dict = {"page_size": page_size}
    if filter is not None:
        body["filter"] = filter
    return await call(
        "notion.db.query",
        {"params": {"data_source_id": data_source_id}, "body": body},
        ctx=ctx,
        dry_run=dry_run,
    )


async def create_page(
    parent_data_source_id: str,
    properties: dict,
    *,
    children: list[dict] | None = None,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    body: dict = {
        "parent": {"type": "data_source_id", "data_source_id": parent_data_source_id},
        "properties": properties,
    }
    if children is not None:
        body["children"] = children
    return await call("notion.page.create", {"body": body}, ctx=ctx, dry_run=dry_run)


async def update_page(
    page_id: str, properties: dict, *, ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    body = {"properties": properties}
    return await call(
        "notion.page.update", {"params": {"page_id": page_id}, "body": body}, ctx=ctx, dry_run=dry_run
    )


async def append_blocks(
    block_id: str, children: list[dict], *, ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    body = {"children": children}
    return await call(
        "notion.blocks.append", {"params": {"block_id": block_id}, "body": body}, ctx=ctx, dry_run=dry_run
    )


async def search(
    query: str, *, filter_object_type: str | None = None, ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    body: dict = {"query": query}
    if filter_object_type is not None:
        body["filter"] = {"property": "object", "value": filter_object_type}
    return await call("notion.search", {"body": body}, ctx=ctx, dry_run=dry_run)


def parse_client_page(page: dict) -> Client:
    """Turns a raw Clients data source page (as returned by query_database) into a Client."""
    properties = page["properties"]
    tier = properties["Tier"]["select"]
    paused_until_raw = properties["Paused Until"]["date"]
    return Client(
        client_id=_plain_text(properties["Client ID"]["rich_text"]),
        name=_plain_text(properties["Name"]["title"]),
        email=properties["Email"]["email"],
        tier=tier["name"] if tier else "New",
        contact_name=_plain_text(properties["Contact Person"]["rich_text"]),
        relationship_notes=_plain_text(properties["Relationship Notes"]["rich_text"]),
        notion_page_id=page["id"],
        paused_until=date.fromisoformat(paused_until_raw["start"]) if paused_until_raw else None,
    )


def md_to_blocks(markdown: str) -> list[dict]:
    """Turns plain paragraphs (one per blank-line-separated chunk) into Notion blocks.

    Deliberately simple: MunimJi's trace/decision text is short prose, not full markdown.
    """
    blocks = []
    for paragraph in markdown.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": paragraph[:2000]}}]},
            }
        )
    return blocks


if __name__ == "__main__":
    import asyncio

    async def _manual_check() -> None:
        ctx = CallCtx(run_id="manual", node="manual")
        result = await search("MunimJi HQ", ctx=ctx, dry_run=True)
        print(result.model_dump_json(indent=2))

    asyncio.run(_manual_check())
