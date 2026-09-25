from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "config" / "tool_registry.yaml"

Risk = Literal["read", "write", "send", "blocked"]


class RegistryEntry(BaseModel):
    id: str
    risk: Risk
    setup_only: bool = False


class UnknownToolError(Exception):
    pass


class BlockedToolError(Exception):
    pass


class ToolRegistry:
    def __init__(self, entries: dict[str, RegistryEntry]):
        self._entries = entries

    def resolve(self, logical: str, *, allow_blocked: bool = False) -> RegistryEntry:
        entry = self._entries.get(logical)
        if entry is None:
            raise UnknownToolError(f"unknown logical tool name: {logical!r}")
        if entry.risk == "blocked" and not allow_blocked:
            raise BlockedToolError(
                f"{logical!r} is risk=blocked and cannot be resolved for normal agent use"
            )
        return entry


def load_registry(path: Path | str = DEFAULT_REGISTRY_PATH) -> ToolRegistry:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    entries = {k: RegistryEntry.model_validate(v) for k, v in raw.items()}
    return ToolRegistry(entries)


@lru_cache
def get_registry() -> ToolRegistry:
    return load_registry()
