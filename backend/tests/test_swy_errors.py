from app.swy.errors import classify, extract_error_json


class _FakeSwytchcodeError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def test_extract_error_json_finds_the_json_line_among_log_lines():
    text = (
        '2026/09/25 21:48:47 [swytchcode exec] request tool=x {"params":{}}\n'
        '{"error":"blocked by policy \\"block-invoice-cancel\\": nope","category":"policy_denied"}\n'
        "2026/09/25 21:48:47 [swytchcode exec] failed tool=x exit_code=6 error=policy violation"
    )
    data = extract_error_json(text)
    assert data == {"error": 'blocked by policy "block-invoice-cancel": nope', "category": "policy_denied"}


def test_extract_error_json_returns_none_when_no_json_present():
    assert extract_error_json("just some plain text, no braces here") is None


def test_classify_policy_denied_extracts_policy_id():
    exc = _FakeSwytchcodeError(
        '{"error":"blocked by policy \\"block-invoice-cancel\\": Cancelling invoices is owner-only.",'
        '"category":"policy_denied"}'
    )
    result = classify(exc)
    assert result.category == "policy_denied"
    assert result.policy_blocked is True
    assert result.policy_id == "block-invoice-cancel"
    assert result.message == "blocked by policy \"block-invoice-cancel\": Cancelling invoices is owner-only."


def test_classify_auth_error_is_not_policy_blocked():
    exc = _FakeSwytchcodeError('{"error":"missing credentials for Gmail","category":"auth"}')
    result = classify(exc)
    assert result.category == "auth"
    assert result.policy_blocked is False
    assert result.policy_id is None


def test_classify_falls_back_to_internal_category_when_no_json():
    exc = _FakeSwytchcodeError("exec: no such file or directory")
    result = classify(exc)
    assert result.category == "internal"
    assert result.message == "exec: no such file or directory"
