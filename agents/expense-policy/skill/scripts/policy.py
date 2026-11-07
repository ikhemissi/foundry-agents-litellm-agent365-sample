"""Contoso's fictional travel expense policy in code: the limits as numbers, and check_expense, which applies them, so
that every figure the expense policy agent states comes from here. Amounts are in euros. The agent runs this script in
the code interpreter (SKILL.md tells it how):
    python policy.py check --category meal --amount 220 --count 4 --with-customers
    python policy.py rules --category hotel --city Paris
Each prints one JSON object; an invalid request prints {"error": "..."} and exits with status 2. Standard library only:
the code interpreter installs nothing."""

import argparse
import json
import sys
from typing import Any

CURRENCY = "EUR"
HOTEL_NIGHTLY_LIMITS = {"paris": 230, "london": 260, "berlin": 180, "lisbon": 160}
HOTEL_NIGHTLY_LIMIT_ELSEWHERE = 150
MEAL_PER_PERSON = 60
MEAL_PER_PERSON_WITH_CUSTOMERS = 90
MEAL_APPROVAL_ABOVE = 500
TRANSPORT_APPROVAL_ABOVE = 300
OTHER_APPROVAL_ABOVE = 50
RECEIPT_ABOVE = 25

RULES = {
    "hotel": [
        "Book a standard room; the nightly rate, taxes included, stays within the city's limit.",
        "A rate above the limit needs your manager's approval before booking.",
    ],
    "meal": [
        (
            f"Up to {MEAL_PER_PERSON} EUR per person, or {MEAL_PER_PERSON_WITH_CUSTOMERS} EUR per person when "
            "customers or partners attend; list the attendees."
        ),
        f"A meal above {MEAL_APPROVAL_ABOVE} EUR in total needs your manager's approval.",
    ],
    "transport": [
        "Take the train in standard class for journeys under four hours; fly economy otherwise.",
        "Taxis and ride-hailing are fine when public transport is impractical.",
        f"A single transport expense above {TRANSPORT_APPROVAL_ABOVE} EUR needs your manager's approval.",
    ],
    "other": [f"Any other expense above {OTHER_APPROVAL_ABOVE} EUR needs your manager's approval."],
}
GENERAL_RULES = [
    f"Keep a receipt for every expense above {RECEIPT_ABOVE} EUR.",
    "File expenses within 30 days of the end of the trip.",
]


class InvalidArguments(ValueError):
    """The request is not one the policy can answer; the message says why, for the model to correct its call."""


def rules(category: str, city: str | None = None) -> dict[str, Any]:
    _check_category(category)
    found: dict[str, Any] = {"category": category, "rules": RULES[category] + GENERAL_RULES, "currency": CURRENCY}
    if category == "hotel":
        found["nightly_limit"] = hotel_limit(city)
        found["city"] = city or "elsewhere"
    if category == "meal":
        found["per_person_limit"] = MEAL_PER_PERSON
        found["per_person_limit_with_customers"] = MEAL_PER_PERSON_WITH_CUSTOMERS
    return found


def check_expense(arguments: dict[str, Any]) -> dict[str, Any]:
    """Whether an expense is within the policy, against which limit, and whether it needs approval or a receipt."""
    category = arguments.get("category")
    _check_category(category)
    amount = arguments.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, int | float) or amount <= 0:
        raise InvalidArguments("amount must be a number above 0.")
    if arguments.get("currency", CURRENCY) != CURRENCY:
        raise InvalidArguments("The policy's limits are in EUR: convert the amount to EUR first.")
    count = arguments.get("count", 1)
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 30:
        raise InvalidArguments("count must be a whole number from 1 to 30 (nights for a hotel, people for a meal).")

    limit, basis = _limit(category, arguments.get("city"), count, bool(arguments.get("with_customers", False)))
    within = amount <= limit
    return {
        "within_policy": within,
        "amount": round(float(amount), 2),
        "limit": limit,
        "limit_basis": basis,
        "needs_manager_approval": not within or _needs_approval(category, amount),
        "receipt_required": amount > RECEIPT_ABOVE,
        "currency": CURRENCY,
    }


def hotel_limit(city: str | None) -> int:
    return HOTEL_NIGHTLY_LIMITS.get((city or "").strip().lower(), HOTEL_NIGHTLY_LIMIT_ELSEWHERE)


def _limit(category: str, city: str | None, count: int, with_customers: bool) -> tuple[float, str]:
    if category == "hotel":
        nightly = hotel_limit(city)
        return nightly * count, f"{nightly} EUR per night in {city or 'this city'}, {count} night(s)"
    if category == "meal":
        per_person = MEAL_PER_PERSON_WITH_CUSTOMERS if with_customers else MEAL_PER_PERSON
        company = "with customers or partners" if with_customers else "employees only"
        return per_person * count, f"{per_person} EUR per person ({company}), {count} person(s)"
    if category == "transport":
        return TRANSPORT_APPROVAL_ABOVE, f"{TRANSPORT_APPROVAL_ABOVE} EUR per expense without approval"
    return OTHER_APPROVAL_ABOVE, f"{OTHER_APPROVAL_ABOVE} EUR per expense without approval"


def _needs_approval(category: str, amount: float) -> bool:
    return category == "meal" and amount > MEAL_APPROVAL_ABOVE


def _check_category(category: Any) -> None:
    if category not in RULES:
        raise InvalidArguments(f"category must be one of {', '.join(RULES)}.")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Contoso's travel expense policy.")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Check one expense against the policy.")
    check.add_argument("--category", required=True, help="hotel, meal, transport or other")
    check.add_argument("--amount", required=True, type=float, help="the total, in EUR")
    check.add_argument("--currency", default=CURRENCY)
    check.add_argument("--city")
    check.add_argument("--count", type=int, default=1, help="nights for a hotel, people for a meal")
    check.add_argument("--with-customers", action="store_true", help="customers or partners attended the meal")
    show = commands.add_parser("rules", help="The rules and limits of a category.")
    show.add_argument("--category", required=True)
    show.add_argument("--city")
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "check":
            result = check_expense(vars(arguments))
        else:
            result = rules(arguments.category, arguments.city)
    except InvalidArguments as error:
        print(json.dumps({"error": str(error)}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
