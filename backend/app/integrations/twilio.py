from app.swy.executor import CallCtx, ToolCallResult, call


async def sms_owner(
    to: str,
    from_: str,
    body: str,
    *,
    account_sid: str | None = None,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    """Hard-coded to the owner's number at the call site (policy also enforces this)."""
    args: dict = {"body": {"To": to, "From": from_, "Body": body}}
    if account_sid is not None:
        args["params"] = {"AccountSid": account_sid}
    return await call("twilio.sms.send", args, ctx=ctx, dry_run=dry_run)


if __name__ == "__main__":
    import asyncio

    async def _manual_check() -> None:
        ctx = CallCtx(run_id="manual", node="manual")
        result = await sms_owner("+919999999999", "+12025550123", "MunimJi: test message", ctx=ctx, dry_run=True)
        print(result.model_dump_json(indent=2))

    asyncio.run(_manual_check())
