import os

from app.governance.allowlist import Allowlist, load_allowlist


def test_email_pattern_matches_plus_addressing():
    allowlist = Allowlist(email_recipients_patterns=["mayankguptawp+*@gmail.com"])
    assert allowlist.is_email_allowed("mayankguptawp+orion@gmail.com") is True
    assert allowlist.is_email_allowed("mayankguptawp+bluepeak@gmail.com") is True


def test_email_pattern_rejects_unrelated_address():
    allowlist = Allowlist(email_recipients_patterns=["mayankguptawp+*@gmail.com"])
    assert allowlist.is_email_allowed("someone.else@gmail.com") is False


def test_email_match_is_case_insensitive():
    allowlist = Allowlist(email_recipients_patterns=["mayankguptawp+*@gmail.com"])
    assert allowlist.is_email_allowed("MayankGuptaWp+Orion@Gmail.com") is True


def test_sms_only_allows_listed_numbers():
    allowlist = Allowlist(sms_recipients=["+919999999999"])
    assert allowlist.is_sms_allowed("+919999999999") is True
    assert allowlist.is_sms_allowed("+911234567890") is False


def test_load_allowlist_substitutes_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("OWNER_PHONE_E164", "+919876543210")
    config_path = tmp_path / "allowlist.yaml"
    config_path.write_text(
        'email_recipients_patterns:\n  - "mayankguptawp+*@gmail.com"\nsms_recipients: ["${OWNER_PHONE_E164}"]\n',
        encoding="utf-8",
    )
    allowlist = load_allowlist(config_path)
    assert allowlist.sms_recipients == ["+919876543210"]
    assert allowlist.is_sms_allowed("+919876543210") is True


def test_load_real_allowlist_config_from_repo():
    os.environ.setdefault("OWNER_PHONE_E164", "+910000000000")
    allowlist = load_allowlist()
    assert allowlist.is_email_allowed("mayankguptawp+orion@gmail.com") is True
