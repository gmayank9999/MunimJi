import asyncio
import json
import re
import shutil
import subprocess
from functools import lru_cache
from typing import Any


@lru_cache
def _swy_path() -> str:
    # shutil.which resolves PATHEXT (.cmd/.exe/...) on Windows, where the bare
    # name "swy" is not directly executable via CreateProcess.
    path = shutil.which("swy")
    if path is None:
        raise FileNotFoundError("swy CLI not found on PATH")
    return path


async def _run_swy(args: list[str]) -> str:
    proc = await asyncio.create_subprocess_exec(
        _swy_path(), *args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    return stdout.decode(errors="replace")


def _parse_jsonl(text: str) -> list[dict[str, Any]]:
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


async def policy_log(n: int = 20) -> list[dict[str, Any]]:
    output = await _run_swy(["audit", "policy", "--json", "-n", str(n)])
    return _parse_jsonl(output)


async def network_log(n: int = 50) -> list[dict[str, Any]]:
    output = await _run_swy(["audit", "network", "--json", "-n", str(n)])
    return _parse_jsonl(output)


_STATS_LINE = re.compile(r"^\s*(Total runs|Successful|Success rate|Last run|Top provider):\s*(.+)$")


async def stats() -> dict[str, str]:
    output = await _run_swy(["audit", "stats"])
    result: dict[str, str] = {}
    for line in output.splitlines():
        match = _STATS_LINE.match(line)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result
