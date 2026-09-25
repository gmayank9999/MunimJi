from app.swy.executor import CallCtx, ToolCallResult, call


async def create_database(
    parent_page_id: str,
    title: str,
    properties: dict,
    *,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    body = {
        "parent": {"page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": title}}],
        "properties": properties,
    }
    return await call("notion.db.create", {"body": body}, ctx=ctx, dry_run=dry_run)


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
    parent_database_id: str,
    properties: dict,
    *,
    children: list[dict] | None = None,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    body: dict = {
        "parent": {"database_id": parent_database_id},
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
