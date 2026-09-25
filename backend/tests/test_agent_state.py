from app.agent.state import InvoiceState, RunState


def test_run_state_accepts_partial_dict():
    state: RunState = {"run_id": "r_1", "prompt": "check all payments", "source": "ui"}
    assert state["run_id"] == "r_1"


def test_invoice_state_accepts_partial_dict():
    state: InvoiceState = {"run_id": "r_1", "decision": "ESCALATE", "rule_id": "R18"}
    assert state["decision"] == "ESCALATE"
