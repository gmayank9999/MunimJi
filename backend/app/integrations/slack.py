from app.swy.executor import CallCtx, ToolCallResult, call


async def post(
    channel: str,
    text: str,
    *,
    blocks: list[dict] | None = None,
    thread_ts: str | None = None,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    body: dict = {"channel": channel, "text": text}
    if blocks is not None:
        body["blocks"] = blocks
    if thread_ts is not None:
        body["thread_ts"] = thread_ts
    return await call("slack.post", {"body": body}, ctx=ctx, dry_run=dry_run)


async def update(
    channel: str,
    ts: str,
    text: str,
    *,
    blocks: list[dict] | None = None,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    body: dict = {"channel": channel, "ts": ts, "text": text}
    if blocks is not None:
        body["blocks"] = blocks
    return await call("slack.update", {"body": body}, ctx=ctx, dry_run=dry_run)


async def history(
    channel: str,
    *,
    oldest: str | None = None,
    limit: int = 100,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    params: dict = {"channel": channel, "limit": limit}
    if oldest is not None:
        params["oldest"] = oldest
    return await call("slack.history", {"params": params}, ctx=ctx, dry_run=dry_run)


async def get_reactions(
    channel: str, timestamp: str, *, ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    params = {"channel": channel, "timestamp": timestamp}
    return await call("slack.reactions.get", {"params": params}, ctx=ctx, dry_run=dry_run)


async def add_reaction(
    channel: str, timestamp: str, name: str, *, ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    body = {"channel": channel, "timestamp": timestamp, "name": name}
    return await call("slack.reactions.add", {"body": body}, ctx=ctx, dry_run=dry_run)


async def list_channels(
    *, exclude_archived: bool = True, ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    params = {"exclude_archived": exclude_archived}
    return await call("slack.channels.list", {"params": params}, ctx=ctx, dry_run=dry_run)


if __name__ == "__main__":
    import asyncio

    async def _manual_check() -> None:
        ctx = CallCtx(run_id="manual", node="manual")
        result = await post("C0000000", "hello from MunimJi", ctx=ctx, dry_run=True)
        print(result.model_dump_json(indent=2))

    asyncio.run(_manual_check())
