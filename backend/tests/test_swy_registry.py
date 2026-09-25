import pytest

from app.swy.registry import BlockedToolError, UnknownToolError, load_registry


@pytest.fixture
def registry():
    return load_registry()


def test_resolves_known_read_tool(registry):
    entry = registry.resolve("paypal.invoices.list")
    assert entry.id == "invoices.invoicing.invoices.list"
    assert entry.risk == "read"


def test_resolves_known_send_tool(registry):
    entry = registry.resolve("gmail.send")
    assert entry.id == "gmail.user.send.create1"
    assert entry.risk == "send"


def test_unknown_logical_raises(registry):
    with pytest.raises(UnknownToolError):
        registry.resolve("not.a.real.tool")


def test_blocked_tool_raises_by_default(registry):
    with pytest.raises(BlockedToolError):
        registry.resolve("paypal.invoices.cancel")


def test_blocked_tool_allowed_with_flag(registry):
    entry = registry.resolve("paypal.invoices.cancel", allow_blocked=True)
    assert entry.risk == "blocked"


def test_setup_only_flag_parsed(registry):
    entry = registry.resolve("paypal.invoices.create")
    assert entry.setup_only is True


def test_all_39_registered_methods_present(registry):
    logical_names = [
        "paypal.invoices.list", "paypal.invoices.search", "paypal.invoices.get",
        "paypal.invoices.create", "paypal.invoices.send", "paypal.invoices.remind",
        "paypal.invoices.record_payment", "paypal.invoices.cancel", "paypal.disputes.list",
        "paypal.captures.refund",
        "gmail.search", "gmail.thread.get", "gmail.get", "gmail.send", "gmail.insert",
        "gmail.labels.list", "gmail.labels.create", "gmail.modify",
        "jira.search", "jira.issue.create", "jira.issue.update", "jira.issue.comment",
        "jira.issue.transitions", "jira.issue.transition",
        "slack.post", "slack.update", "slack.history", "slack.reactions.get",
        "slack.reactions.add", "slack.channels.list",
        "notion.db.create", "notion.db.query", "notion.page.create", "notion.page.update",
        "notion.blocks.append", "notion.search",
        "sheets.append", "sheets.get",
        "twilio.sms.send",
    ]
    assert len(logical_names) == 39
    for name in logical_names:
        registry.resolve(name, allow_blocked=True)
