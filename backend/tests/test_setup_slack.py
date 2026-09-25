import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from setup_slack import CHANNEL_KEYS, WELCOME_MESSAGES  # noqa: E402


def test_every_channel_has_a_welcome_message():
    assert set(CHANNEL_KEYS.keys()) == set(WELCOME_MESSAGES.keys())


def test_channel_keys_cover_the_four_plan_channels():
    assert set(CHANNEL_KEYS.keys()) == {
        "finance-ops", "munimji-approvals", "munimji-audit", "munimji",
    }


def test_channel_keys_are_unique():
    assert len(set(CHANNEL_KEYS.values())) == len(CHANNEL_KEYS)
