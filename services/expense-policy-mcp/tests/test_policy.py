"""Contoso's policy in numbers: the sample's two questions (a Paris hotel, a dinner for four) and the edge cases."""

import policy
import pytest


def check(**arguments):
    return policy.check_expense(arguments)


def test_a_paris_hotel_at_210_a_night_is_within_the_limit():
    result = check(category="hotel", amount=630, city="Paris", count=3)

    assert (result["within_policy"], result["limit"], result["needs_manager_approval"]) == (True, 690, False)
    assert result["limit_basis"] == "230 EUR per night in Paris, 3 night(s)"


def test_a_dinner_for_four_with_a_customer_is_within_the_limit_and_needs_a_receipt():
    result = check(category="meal", amount=220, count=4, with_customers=True)

    assert (result["within_policy"], result["limit"], result["receipt_required"]) == (True, 360, True)


def test_the_same_dinner_for_employees_only_is_over_the_limit():
    result = check(category="meal", amount=260, count=4)

    assert (result["within_policy"], result["limit"], result["needs_manager_approval"]) == (False, 240, True)


def test_a_large_meal_within_the_per_person_limit_still_needs_approval():
    result = check(category="meal", amount=540, count=8, with_customers=True)

    assert result["within_policy"] is True and result["needs_manager_approval"] is True


def test_an_unlisted_city_gets_the_default_hotel_limit():
    assert policy.get_policy("hotel", "Oslo")["nightly_limit"] == 150


def test_small_expenses_need_no_receipt():
    assert check(category="transport", amount=18.5)["receipt_required"] is False


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"category": "gift", "amount": 10}, "category must be one of"),
        ({"category": "meal", "amount": -5}, "amount must be"),
        ({"category": "meal", "amount": 50, "currency": "USD"}, "convert the amount to EUR"),
        ({"category": "hotel", "amount": 50, "count": 0}, "count must be"),
    ],
)
def test_invalid_checks_are_refused_with_a_reason(arguments, message):
    with pytest.raises(policy.InvalidArguments, match=message):
        policy.check_expense(arguments)
