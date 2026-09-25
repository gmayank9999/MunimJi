from datetime import date

from app.integrations.notion import parse_client_page

SAMPLE_CLIENT_PAGE = {
    "id": "3e60c11b-60e1-8102-b7b7-e33ec8536265",
    "properties": {
        "Client ID": {"rich_text": [{"plain_text": "C08"}], "type": "rich_text"},
        "Contact Person": {"rich_text": [{"plain_text": "Ananya Rao"}], "type": "rich_text"},
        "Email": {"email": "kaarigar.clients.sim+zephyr@gmail.com", "type": "email"},
        "Name": {"title": [{"plain_text": "Zephyr Hotels"}], "type": "title"},
        "Paused Until": {"date": None, "type": "date"},
        "Payment Behaviour": {"select": {"name": "Prompt"}, "type": "select"},
        "Relationship Notes": {"rich_text": [], "type": "rich_text"},
        "Tier": {"select": {"name": "VIP"}, "type": "select"},
    },
}


def test_parse_client_page_basic_fields():
    client = parse_client_page(SAMPLE_CLIENT_PAGE)
    assert client.client_id == "C08"
    assert client.name == "Zephyr Hotels"
    assert client.email == "kaarigar.clients.sim+zephyr@gmail.com"
    assert client.tier == "VIP"
    assert client.contact_name == "Ananya Rao"
    assert client.notion_page_id == "3e60c11b-60e1-8102-b7b7-e33ec8536265"


def test_parse_client_page_blank_relationship_notes():
    client = parse_client_page(SAMPLE_CLIENT_PAGE)
    assert client.relationship_notes == ""


def test_parse_client_page_no_paused_until():
    client = parse_client_page(SAMPLE_CLIENT_PAGE)
    assert client.paused_until is None


def test_parse_client_page_with_paused_until():
    page = {
        **SAMPLE_CLIENT_PAGE,
        "properties": {
            **SAMPLE_CLIENT_PAGE["properties"],
            "Paused Until": {"date": {"start": "2026-10-05"}, "type": "date"},
        },
    }
    client = parse_client_page(page)
    assert client.paused_until == date(2026, 10, 5)


def test_parse_client_page_multi_fragment_rich_text():
    page = {
        **SAMPLE_CLIENT_PAGE,
        "properties": {
            **SAMPLE_CLIENT_PAGE["properties"],
            "Relationship Notes": {
                "rich_text": [{"plain_text": "Long-time "}, {"plain_text": "client."}],
                "type": "rich_text",
            },
        },
    }
    client = parse_client_page(page)
    assert client.relationship_notes == "Long-time client."
