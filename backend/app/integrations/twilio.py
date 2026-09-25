from app.settings import get_settings
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
    """Hard-coded to the owner's number at the call site (policy also enforces this).

    AccountSid is not auto-injected by Swytchcode from the connected credentials -
    Twilio's Messages.create needs it explicitly as a path param (confirmed live:
    calling without it fails with "missing required field AccountSid").
    """
    account_sid = account_sid or get_settings().twilio_account_sid
    args: dict = {
        "params": {"AccountSid": account_sid},
        "body": {"To": to, "From": from_, "Body": body},
    }
    return await call("twilio.sms.send", args, ctx=ctx, dry_run=dry_run)


if __name__ == "__main__":
    import asyncio

    async def _manual_check() -> None:
        ctx = CallCtx(run_id="manual", node="manual")
        result = await sms_owner(
            "+919999999999", "+12025550123", "MunimJi: test message", ctx=ctx, dry_run=True
        )
        print(result.model_dump_json(indent=2))

    asyncio.run(_manual_check())
