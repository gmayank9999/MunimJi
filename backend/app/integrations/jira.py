from app.swy.executor import CallCtx, ToolCallResult, call


async def search(
    jql: str,
    *,
    max_results: int = 50,
    fields: list[str] | None = None,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    body: dict = {"jql": jql, "maxResults": max_results}
    if fields is not None:
        body["fields"] = fields
    return await call("jira.search", {"body": body}, ctx=ctx, dry_run=dry_run)


async def create_issue(
    project_key: str,
    summary: str,
    *,
    issue_type: str = "Task",
    description_adf: dict | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    fields: dict = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
    }
    if description_adf is not None:
        fields["description"] = description_adf
    if priority is not None:
        fields["priority"] = {"name": priority}
    if labels is not None:
        fields["labels"] = labels
    return await call("jira.issue.create", {"body": {"fields": fields}}, ctx=ctx, dry_run=dry_run)


async def update_issue(
    issue_key: str,
    *,
    priority: str | None = None,
    fields: dict | None = None,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    payload_fields: dict = dict(fields or {})
    if priority is not None:
        payload_fields["priority"] = {"name": priority}
    return await call(
        "jira.issue.update",
        {"params": {"issueIdOrKey": issue_key}, "body": {"fields": payload_fields}},
        ctx=ctx,
        dry_run=dry_run,
    )


async def comment(
    issue_key: str, body_adf: dict, *, ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    return await call(
        "jira.issue.comment",
        {"params": {"issueIdOrKey": issue_key}, "body": {"body": body_adf}},
        ctx=ctx,
        dry_run=dry_run,
    )


async def list_transitions(issue_key: str, *, ctx: CallCtx, dry_run: bool = False) -> ToolCallResult:
    return await call(
        "jira.issue.transitions", {"params": {"issueIdOrKey": issue_key}}, ctx=ctx, dry_run=dry_run
    )


async def transition(
    issue_key: str, transition_id: str, *, ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    body = {"transition": {"id": transition_id}}
    return await call(
        "jira.issue.transition",
        {"params": {"issueIdOrKey": issue_key}, "body": body},
        ctx=ctx,
        dry_run=dry_run,
    )


def to_adf(text: str) -> dict:
    """Plain paragraphs (blank-line separated) to Atlassian Document Format."""
    content = []
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        content.append({"type": "paragraph", "content": [{"type": "text", "text": paragraph}]})
    return {"type": "doc", "version": 1, "content": content}


if __name__ == "__main__":
    import asyncio

    async def _manual_check() -> None:
        ctx = CallCtx(run_id="manual", node="manual")
        result = await search("project = FIN", ctx=ctx, dry_run=True)
        print(result.model_dump_json(indent=2))

    asyncio.run(_manual_check())
