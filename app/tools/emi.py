"""Pricing/EMI Tool — deterministic amortization math (engineering rule 5).

Standard reducing-balance formula: EMI = P·r·(1+r)^n / ((1+r)^n − 1), where r
is the monthly rate and n the tenure in months. No LLM is ever involved in
these numbers. Defaults are stated assumptions and must be repeated in any
customer-facing reply that uses them.
"""

from pydantic import BaseModel, ConfigDict

DEFAULT_ANNUAL_RATE_PERCENT = 8.5
DEFAULT_TENURE_YEARS = 20
DEFAULT_DOWN_PAYMENT_PERCENT = 20
MONTHS_PER_YEAR = 12


class EMIQuote(BaseModel):
    model_config = ConfigDict(frozen=True)

    principal: int
    annual_rate_percent: float
    tenure_months: int
    monthly_emi: int
    total_payment: int
    total_interest: int


def calculate_emi(
    principal: int, annual_rate_percent: float, tenure_months: int
) -> EMIQuote:
    if principal <= 0:
        raise ValueError("principal must be positive")
    if annual_rate_percent < 0:
        raise ValueError("annual_rate_percent cannot be negative")
    if tenure_months <= 0:
        raise ValueError("tenure_months must be positive")

    monthly_rate = annual_rate_percent / MONTHS_PER_YEAR / 100
    if monthly_rate == 0:
        raw_emi = principal / tenure_months
    else:
        growth = (1 + monthly_rate) ** tenure_months
        raw_emi = principal * monthly_rate * growth / (growth - 1)

    monthly_emi = round(raw_emi)
    total_payment = monthly_emi * tenure_months
    return EMIQuote(
        principal=principal,
        annual_rate_percent=annual_rate_percent,
        tenure_months=tenure_months,
        monthly_emi=monthly_emi,
        total_payment=total_payment,
        total_interest=total_payment - principal,
    )


def quote_for_property_price(
    price: int,
    down_payment_percent: float = DEFAULT_DOWN_PAYMENT_PERCENT,
    annual_rate_percent: float = DEFAULT_ANNUAL_RATE_PERCENT,
    tenure_years: int = DEFAULT_TENURE_YEARS,
) -> EMIQuote:
    """EMI on the loan portion of a property price after the down payment."""
    if price <= 0:
        raise ValueError("price must be positive")
    if not 0 <= down_payment_percent < 100:
        raise ValueError("down_payment_percent must be in [0, 100)")

    principal = round(price * (1 - down_payment_percent / 100))
    return calculate_emi(principal, annual_rate_percent, tenure_years * MONTHS_PER_YEAR)
