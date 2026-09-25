"""Run-scoped dependencies injected into every graph node via LangGraph's Runtime
context (not graph state - these are services, not data that gets checkpointed)."""

from dataclasses import dataclass

from app.clock import Clock
from app.db import Database
from app.events import EventBus
from app.governance.allowlist import Allowlist
from app.governance.ledger import Ledger
from app.policy.config import PolicyConfig
from app.policy.router import FeatureFlags


@dataclass
class GraphContext:
    db: Database
    bus: EventBus
    ledger: Ledger
    allowlist: Allowlist
    policy_config: PolicyConfig
    flags: FeatureFlags
    clock: Clock
    run_id: str
    dry_run_sends: bool = False
    demo_epoch: int = 1
    llm_cache: bool = False
