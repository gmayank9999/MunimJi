"""Offline unit tests for the real-call response envelope handling: swytchcode_runtime
does not raise for provider-level HTTP errors (only pre-flight auth/policy failures do),
so `_interpret_response` has to detect and unwrap this itself. See docs/swytchcode-notes.md.
"""

from app.swy.executor import _interpret_response


def test_dry_run_preview_is_always_ok():
    raw = {"headers": {"Authorization": "[REDACTED]"}, "method": "GET", "url": "https://api.stripe.com/v1/invoices"}
    result = _interpret_response(raw, dry_run=True)
    assert result["ok"] is True
    assert result["data"] == raw


def test_real_success_unwraps_inner_data():
    raw = {
        "data": {"data": [], "has_more": False, "object": "list"},
        "request": {"method": "GET", "url": "https://api.stripe.com/v1/invoices"},
        "status_code": 200,
    }
    result = _interpret_response(raw, dry_run=False)
    assert result["ok"] is True
    assert result["data"] == {"data": [], "has_more": False, "object": "list"}


def test_real_provider_error_is_detected_even_without_exception():
    raw = {
        "data": {
            "code": "validation_error",
            "message": "Creating new databases with data sources is not supported...",
            "object": "error",
            "status": 400,
        },
        "error_category": "validation",
        "request": {"method": "POST", "url": "https://api.notion.com/v1/data_sources"},
        "retryable": False,
        "status_code": 400,
        "suggested_action": "the request was rejected; check the arguments against the tool's input schema",
    }
    result = _interpret_response(raw, dry_run=False)
    assert result["ok"] is False
    assert result["category"] == "validation"
    assert "not supported" in result["error"]
    assert result["policy_blocked"] is False


def test_real_error_without_dict_inner_data_falls_back_to_str():
    raw = {"data": "plain text error", "error_category": "internal", "status_code": 500}
    result = _interpret_response(raw, dry_run=False)
    assert result["ok"] is False
    assert result["error"] == "plain text error"


def test_real_error_missing_message_falls_back_to_status_code():
    raw = {"data": {}, "error_category": "internal", "status_code": 503}
    result = _interpret_response(raw, dry_run=False)
    assert result["ok"] is False
    assert result["error"] == "HTTP 503"


def test_non_envelope_dict_is_passed_through_as_ok():
    raw = {"some": "other", "shape": True}
    result = _interpret_response(raw, dry_run=False)
    assert result["ok"] is True
    assert result["data"] == raw


def test_non_dict_response_is_passed_through_as_ok():
    result = _interpret_response("raw text response", dry_run=False)
    assert result["ok"] is True
    assert result["data"] == "raw text response"
