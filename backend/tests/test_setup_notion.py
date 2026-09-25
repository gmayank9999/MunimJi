import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from setup_notion import CLIENTS_PROPERTIES, DB_KEYS, _title_text  # noqa: E402


def test_title_text_strips_leading_newline_from_slash_command_residue():
    obj = {
        "title": [
            {"plain_text": "\n"},
            {"plain_text": "Clients"},
        ]
    }
    assert _title_text(obj) == "Clients"


def test_title_text_handles_plain_single_segment():
    assert _title_text({"title": [{"plain_text": "Invoices Ledger"}]}) == "Invoices Ledger"


def test_title_text_empty_when_no_title():
    assert _title_text({}) == ""


def test_db_keys_cover_all_four_databases():
    assert set(DB_KEYS.keys()) == {"Clients", "Invoices Ledger", "Decision Traces", "Run Reports"}


def test_clients_properties_do_not_redeclare_title():
    # "Name" is the built-in title column created by Notion's UI - re-declaring it
    # in an update call would try to change the title property's type and fail.
    assert "Name" not in CLIENTS_PROPERTIES
