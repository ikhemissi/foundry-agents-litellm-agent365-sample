"""Contoso's fictional travel expense policy: the rules as text for the model to quote, and the limits as numbers that
check_expense applies in code, so that every figure in an answer comes from here. Amounts are in euros."""

from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

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


class InvalidArguments(ToolError):
    """The tool was called with arguments it does not accept. A ToolError, so that MCP shows the message to the caller
    (the model can then correct its call); any other exception reaches it only as "Error executing tool"."""


def get_policy(category: str, city: str | None = None) -> dict[str, Any]:
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
