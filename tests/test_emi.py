"""Task 3 done-when: unit tests match hand-calculated EMI values.

Hand calculations (standard reducing-balance formula):
- ₹50,00,000 at 9% for 240 months  -> EMI ₹44,986
- ₹10,00,000 at 12% for 12 months  -> EMI ₹88,849
"""

import pytest

from app.tools.emi import calculate_emi, quote_for_property_price


class TestCalculateEMI:
    def test_matches_hand_calculated_home_loan(self):
        quote = calculate_emi(5_000_000, 9.0, 240)
        assert quote.monthly_emi == 44_986

    def test_matches_hand_calculated_short_loan(self):
        quote = calculate_emi(1_000_000, 12.0, 12)
        assert quote.monthly_emi == 88_849

    def test_zero_rate_is_simple_division(self):
        quote = calculate_emi(1_200_000, 0.0, 12)
        assert quote.monthly_emi == 100_000
        assert quote.total_interest == 0

    def test_totals_are_consistent(self):
        quote = calculate_emi(5_000_000, 9.0, 240)
        assert quote.total_payment == quote.monthly_emi * 240
        assert quote.total_interest == quote.total_payment - 5_000_000

    @pytest.mark.parametrize(
        ("principal", "rate", "months"),
        [(0, 9.0, 240), (-100, 9.0, 240), (5_000_000, -1.0, 240), (5_000_000, 9.0, 0)],
    )
    def test_invalid_inputs_fail_fast(self, principal, rate, months):
        with pytest.raises(ValueError):
            calculate_emi(principal, rate, months)


class TestQuoteForPropertyPrice:
    def test_default_down_payment_reduces_principal(self):
        # Property #4 (Bopal 3BHK, ₹85,00,000) with 20% down -> loan ₹68,00,000.
        quote = quote_for_property_price(8_500_000)
        assert quote.principal == 6_800_000
        assert quote.annual_rate_percent == 8.5
        assert quote.tenure_months == 240

    def test_emi_for_property_4_at_stated_assumptions(self):
        quote = quote_for_property_price(8_500_000)
        # Hand-checked: ₹68,00,000 at 8.5% for 240 months -> ₹59,012 per month.
        assert quote.monthly_emi == 59_012

    def test_invalid_price_or_down_payment_fail_fast(self):
        with pytest.raises(ValueError):
            quote_for_property_price(0)
        with pytest.raises(ValueError):
            quote_for_property_price(8_500_000, down_payment_percent=100)
