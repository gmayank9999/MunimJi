import os

import pytest

from app.reasoning.interpreter import interpret
from tests.reasoning.golden_set import GOLDEN_SET

pytestmark = pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"), reason="requires a live GROQ_API_KEY for the interpreter eval"
)


async def test_interpreter_golden_set_accuracy():
    correct = 0
    misses: list[str] = []
    for message, expected, msg_date in GOLDEN_SET:
        signal = await interpret([message], msg_date)
        if signal.category == expected:
            correct += 1
        else:
            misses.append(f"{message!r} -> expected {expected}, got {signal.category}")

    accuracy = correct / len(GOLDEN_SET)
    print(f"\ninterpreter golden set accuracy: {accuracy:.0%} ({correct}/{len(GOLDEN_SET)})")
    for miss in misses:
        print(f"  miss: {miss}")

    assert accuracy >= 0.9, f"accuracy {accuracy:.0%} below 90% threshold; misses: {misses}"
