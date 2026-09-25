from app.swy.executor import CallCtx, ToolCallResult, call


async def append_rows(
    spreadsheet_id: str,
    range_: str,
    rows: list[list],
    *,
    value_input_option: str = "USER_ENTERED",
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    params = {
        "spreadsheetId": spreadsheet_id,
        "range": range_,
        "valueInputOption": value_input_option,
        "insertDataOption": "INSERT_ROWS",
    }
    body = {"values": rows}
    return await call("sheets.append", {"params": params, "body": body}, ctx=ctx, dry_run=dry_run)


async def get_values(
    spreadsheet_id: str, range_: str, *, ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    params = {"spreadsheetId": spreadsheet_id, "range": range_}
    return await call("sheets.get", {"params": params}, ctx=ctx, dry_run=dry_run)


if __name__ == "__main__":
    import asyncio

    async def _manual_check() -> None:
        ctx = CallCtx(run_id="manual", node="manual")
        result = await get_values("dummy-sheet-id", "Payments!A1:F1", ctx=ctx, dry_run=True)
        print(result.model_dump_json(indent=2))

    asyncio.run(_manual_check())
