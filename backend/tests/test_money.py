from decimal import Decimal

from app.money import Money, format_inr, usd_to_inr


def test_format_inr_small():
    assert format_inr(0) == "₹0"
    assert format_inr(8) == "₹8"
    assert format_inr(800) == "₹800"


def test_format_inr_thousands():
    assert format_inr(8000) == "₹8,000"
    assert format_inr(22000) == "₹22,000"


def test_format_inr_lakh():
    assert format_inr(123456) == "₹1,23,456"
    assert format_inr(850000) == "₹8,50,000"


def test_format_inr_crore():
    assert format_inr(12345678) == "₹1,23,45,678"


def test_format_inr_negative():
    assert format_inr(-4000) == "-₹4,000"


def test_usd_to_inr_rounds_half_up():
    assert usd_to_inr(Decimal("100"), Decimal("83.0")) == 8300
    assert usd_to_inr(Decimal("10.505"), Decimal("2")) == 21


def test_money_from_amount_inr():
    m = Money.from_amount("15000", "INR")
    assert m.inr == 15000
    assert m.currency == "INR"
    assert str(m) == "₹15,000"


def test_money_from_amount_usd_converts():
    m = Money.from_amount("1000", "usd", fx_inr_per_usd="83")
    assert m.currency == "USD"
    assert m.inr == 83000


def test_money_unsupported_currency_raises():
    try:
        Money.from_amount("10", "EUR")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unsupported currency")
