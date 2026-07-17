"""INR units and display formatting."""

LAKH = 100_000
CRORE = 10_000_000


def format_inr(amount: int) -> str:
    """Human format: ₹65 lakh, ₹1.2 crore, ₹73.63 lakh, ₹45,000."""
    for unit_value, unit_name in ((CRORE, "crore"), (LAKH, "lakh")):
        if amount >= unit_value:
            value = round(amount / unit_value, 2)
            return f"₹{value:g} {unit_name}"
    return f"₹{amount:,}"
