from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

RUPEE = "₹"


def format_inr(amount: int) -> str:
    """Format an integer rupee amount using Indian digit grouping.

    1234567 -> '₹12,34,567'
    """
    sign = "-" if amount < 0 else ""
    digits = str(abs(amount))
    if len(digits) <= 3:
        grouped = digits
    else:
        last3 = digits[-3:]
        rest = digits[:-3]
        parts: list[str] = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        grouped = ",".join(parts) + "," + last3
    return f"{sign}{RUPEE}{grouped}"


def usd_to_inr(usd: Decimal | float | str, fx_inr_per_usd: Decimal | float | str) -> int:
    value = Decimal(str(usd)) * Decimal(str(fx_inr_per_usd))
    return int(value.to_integral_value(rounding=ROUND_HALF_UP))


class Money(BaseModel):
    """An amount in its original currency, normalised to an INR integer for policy math."""

    value: Decimal
    currency: str
    inr: int

    def __str__(self) -> str:
        return format_inr(self.inr)

    @classmethod
    def from_amount(
        cls,
        value: Decimal | float | str,
        currency: str,
        fx_inr_per_usd: Decimal | float | str = Decimal("83.0"),
    ) -> "Money":
        decimal_value = Decimal(str(value))
        currency = currency.upper()
        if currency == "INR":
            inr = int(decimal_value.to_integral_value(rounding=ROUND_HALF_UP))
        elif currency == "USD":
            inr = usd_to_inr(decimal_value, fx_inr_per_usd)
        else:
            raise ValueError(f"unsupported currency: {currency}")
        return cls(value=decimal_value, currency=currency, inr=inr)
