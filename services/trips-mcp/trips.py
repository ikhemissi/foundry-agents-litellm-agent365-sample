"""Each user's business trips and their expenses, kept in two Azure Tables partitioned by user: the logic behind the
MCP tools, testable with fake tables. A user who has no trips yet gets three fictional ones (Contoso's sample data),
dated around today, so that the sample has something to talk about."""

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from azure.core.exceptions import ResourceNotFoundError
from mcp.server.mcpserver.exceptions import ToolError

CATEGORIES = ("hotel", "meal", "transport", "other")
MAX_AMOUNT = 5000
MAX_DESCRIPTION_LENGTH = 200
MAX_ATTENDEES = 20
TRIP_ID = re.compile(r"^TRIP-\d{4}$")
CURRENCY = re.compile(r"^[A-Z]{3}$")


class InvalidArguments(ToolError):
    """The tool was called with arguments it does not accept. A ToolError, so that MCP shows the message to the caller
    (the model can then correct its call); any other exception reaches it only as "Error executing tool"."""


class Table(Protocol):
    def upsert_entity(self, entity: dict[str, Any]) -> Any: ...
    def create_entity(self, entity: dict[str, Any]) -> Any: ...
    def get_entity(self, partition_key: str, row_key: str) -> dict[str, Any]: ...
    def query_entities(self, query_filter: str, *, parameters: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class User:
    """The signed-in user, from the claims of a validated token. Users are told apart by tenant and object id."""

    tenant_id: str
    object_id: str

    @property
    def partition(self) -> str:
        return f"{self.tenant_id}_{self.object_id}"


def sample_trips(today: date) -> list[dict[str, Any]]:
    """Contoso's fictional trips for a new user: one next week, one next month, one last month."""
    next_monday = today + timedelta(days=7 - today.weekday())
    in_a_month = next_monday + timedelta(days=28)
    last_month = next_monday - timedelta(days=35)
    return [
        _trip("TRIP-1001", "Paris", "Customer workshop", next_monday, nights=3, hotel="Hotel Lumière", rate=210),
        _trip("TRIP-1002", "Lisbon", "Team offsite", in_a_month, nights=2, hotel="Casa do Rio", rate=150),
        _trip("TRIP-1003", "Berlin", "Partner conference", last_month, nights=2, hotel="Spree Hotel", rate=175),
    ]


def _trip(trip_id: str, city: str, purpose: str, start: date, nights: int, hotel: str, rate: int) -> dict[str, Any]:
    return {
        "RowKey": trip_id,
        "City": city,
        "Purpose": purpose,
        "Start": start.isoformat(),
        "End": (start + timedelta(days=nights)).isoformat(),
        "Hotel": hotel,
        "HotelNightlyRate": rate,
        "Currency": "EUR",
    }


def list_trips(trips: Table, user: User, today: date | None = None) -> list[dict[str, Any]]:
    found = _query(trips, user)
    if not found:
        for trip in sample_trips(today or datetime.now(UTC).date()):
            # Upserts with fixed ids: two first calls at the same time still give the user exactly three trips.
            trips.upsert_entity({"PartitionKey": user.partition, **trip})
        found = _query(trips, user)
    return sorted((_trip_view(entity, today) for entity in found), key=lambda trip: trip["start"])


def get_trip(trips: Table, expenses: Table, user: User, trip_id: str, today: date | None = None) -> dict[str, Any]:
    entity = _get_trip_entity(trips, user, trip_id)
    filed = [
        _expense_view(expense)
        for expense in expenses.query_entities(
            "PartitionKey eq @PartitionKey and TripId eq @TripId",
            parameters={"PartitionKey": user.partition, "TripId": entity["RowKey"]},
        )
    ]
    return {
        **_trip_view(entity, today),
        "expenses": sorted(filed, key=lambda expense: expense["filed_at"]),
        "expenses_total": round(sum(expense["amount"] for expense in filed), 2),
    }


def add_expense(
    trips: Table, expenses: Table, user: User, arguments: dict[str, Any], now: datetime | None = None
) -> dict[str, Any]:
    expense = _expense_to_add(arguments)
    trip = _get_trip_entity(trips, user, expense["trip_id"])
    filed_at = (now or datetime.now(UTC)).isoformat()
    expense_id = f"EXP-{uuid.uuid4().hex[:8].upper()}"
    expenses.create_entity(
        {
            "PartitionKey": user.partition,
            "RowKey": expense_id,
            "TripId": trip["RowKey"],
            "Category": expense["category"],
            "Amount": expense["amount"],
            "Currency": expense["currency"],
            "Description": expense["description"],
            "Attendees": expense["attendees"],
            "FiledAt": filed_at,
        }
    )
    return {"id": expense_id, **expense, "filed_at": filed_at}


def _query(trips: Table, user: User) -> list[dict[str, Any]]:
    return list(trips.query_entities("PartitionKey eq @PartitionKey", parameters={"PartitionKey": user.partition}))


def _get_trip_entity(trips: Table, user: User, trip_id: Any) -> dict[str, Any]:
    if not isinstance(trip_id, str) or not TRIP_ID.match(trip_id):
        raise InvalidArguments("trip_id must look like TRIP-1001: call list_trips to get the user's trips.")
    try:
        return trips.get_entity(partition_key=user.partition, row_key=trip_id)
    except ResourceNotFoundError:
        raise InvalidArguments(f"The user has no trip {trip_id}: call list_trips to get the user's trips.") from None


def _expense_to_add(arguments: dict[str, Any]) -> dict[str, Any]:
    category = arguments.get("category")
    if category not in CATEGORIES:
        raise InvalidArguments(f"category must be one of {', '.join(CATEGORIES)}.")
    amount = arguments.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, int | float) or not 0 < amount <= MAX_AMOUNT:
        raise InvalidArguments(f"amount must be a number above 0 and at most {MAX_AMOUNT}.")
    currency = arguments.get("currency", "EUR")
    if not isinstance(currency, str) or not CURRENCY.match(currency):
        raise InvalidArguments("currency must be a three-letter code such as EUR.")
    description = arguments.get("description")
    if not isinstance(description, str) or not description.strip():
        raise InvalidArguments("description is required.")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise InvalidArguments(f"description must be at most {MAX_DESCRIPTION_LENGTH} characters.")
    attendees = arguments.get("attendees", 1)
    if isinstance(attendees, bool) or not isinstance(attendees, int) or not 1 <= attendees <= MAX_ATTENDEES:
        raise InvalidArguments(f"attendees must be a whole number from 1 to {MAX_ATTENDEES}.")
    return {
        "trip_id": arguments.get("trip_id"),
        "category": category,
        "amount": round(float(amount), 2),
        "currency": currency,
        "description": description.strip(),
        "attendees": attendees,
    }


def _trip_view(entity: dict[str, Any], today: date | None) -> dict[str, Any]:
    end = date.fromisoformat(entity["End"])
    return {
        "id": entity["RowKey"],
        "city": entity["City"],
        "purpose": entity["Purpose"],
        "start": entity["Start"],
        "end": entity["End"],
        "status": "completed" if end < (today or datetime.now(UTC).date()) else "upcoming",
        "hotel": entity["Hotel"],
        "hotel_nightly_rate": entity["HotelNightlyRate"],
        "currency": entity["Currency"],
    }


def _expense_view(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entity["RowKey"],
        "category": entity["Category"],
        "amount": entity["Amount"],
        "currency": entity["Currency"],
        "description": entity["Description"],
        "attendees": entity["Attendees"],
        "filed_at": entity["FiledAt"],
    }
