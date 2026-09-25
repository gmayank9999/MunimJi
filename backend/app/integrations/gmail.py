import base64
from email.mime.text import MIMEText

from app.swy.executor import CallCtx, ToolCallResult, call


async def search(
    query: str, *, max_results: int = 20, user_id: str = "me", ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    params = {"userId": user_id, "q": query, "maxResults": max_results}
    return await call("gmail.search", {"params": params}, ctx=ctx, dry_run=dry_run)


async def get_thread(
    thread_id: str, *, user_id: str = "me", ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    params = {"userId": user_id, "id": thread_id}
    return await call("gmail.thread.get", {"params": params}, ctx=ctx, dry_run=dry_run)


async def get_message(
    message_id: str, *, user_id: str = "me", ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    params = {"userId": user_id, "id": message_id}
    return await call("gmail.get", {"params": params}, ctx=ctx, dry_run=dry_run)


def build_raw(
    *,
    to: str,
    from_: str,
    subject: str,
    body: str,
    idem_key: str,
    decision: str,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> str:
    """RFC822 message, base64url-encoded, with MunimJi's tracing headers set."""
    msg = MIMEText(body)
    msg["To"] = to
    msg["From"] = from_
    msg["Subject"] = subject
    msg["Message-ID"] = f"<munimji-{idem_key}@kaarigar.studio>"
    msg["X-MunimJi-Decision"] = decision
    msg["X-MunimJi-Key"] = idem_key
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


async def send(
    raw: str,
    *,
    thread_id: str | None = None,
    user_id: str = "me",
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    body: dict = {"raw": raw}
    if thread_id is not None:
        body["threadId"] = thread_id
    return await call("gmail.send", {"params": {"userId": user_id}, "body": body}, ctx=ctx, dry_run=dry_run)


async def insert(
    raw: str,
    *,
    user_id: str = "me",
    label_ids: list[str] | None = None,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    body: dict = {"raw": raw}
    if label_ids is not None:
        body["labelIds"] = label_ids
    return await call("gmail.insert", {"params": {"userId": user_id}, "body": body}, ctx=ctx, dry_run=dry_run)


async def list_labels(*, user_id: str = "me", ctx: CallCtx, dry_run: bool = False) -> ToolCallResult:
    return await call("gmail.labels.list", {"params": {"userId": user_id}}, ctx=ctx, dry_run=dry_run)


async def create_label(
    name: str, *, user_id: str = "me", ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    body = {"name": name}
    return await call(
        "gmail.labels.create", {"params": {"userId": user_id}, "body": body}, ctx=ctx, dry_run=dry_run
    )


async def modify(
    message_id: str,
    *,
    add_label_ids: list[str] | None = None,
    remove_label_ids: list[str] | None = None,
    user_id: str = "me",
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    body: dict = {}
    if add_label_ids is not None:
        body["addLabelIds"] = add_label_ids
    if remove_label_ids is not None:
        body["removeLabelIds"] = remove_label_ids
    params = {"userId": user_id, "id": message_id}
    return await call("gmail.modify", {"params": params, "body": body}, ctx=ctx, dry_run=dry_run)


def find_sent_query(message_id_header: str) -> str:
    """Gmail search query to find a message by its Message-ID header (for crash recovery)."""
    return f"rfc822msgid:{message_id_header}"


if __name__ == "__main__":
    import asyncio

    async def _manual_check() -> None:
        ctx = CallCtx(run_id="manual", node="manual")
        result = await search("from:orion@example.com", ctx=ctx, dry_run=True)
        print(result.model_dump_json(indent=2))

    asyncio.run(_manual_check())
