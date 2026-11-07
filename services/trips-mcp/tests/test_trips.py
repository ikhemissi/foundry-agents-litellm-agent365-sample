"""The trips logic with in-memory tables: sample data per user, users kept apart, expenses checked before filing."""

from datetime import UTC, date, datetime

import pytest
import trips

from tests.fakes import FakeTable

ALICE = trips.User(tenant_id="tenant", object_id="alice")
BOB = trips.User(tenant_id="tenant", object_id="bob")
TODAY = date(2026, 11, 7)  # a Saturday
DINNER = {
    "trip_id": "TRIP-1001",
    "category": "meal",
    "amount": 220,
    "description": "Dinner with the customer",
    "attendees": 4,
}


@pytest.fixture
def tables():
    return FakeTable(), FakeTable()


def test_a_new_user_gets_three_sample_trips_dated_around_today(tables):
    listed = trips.list_trips(tables[0], ALICE, TODAY)

    assert [trip["city"] for trip in listed] == ["Berlin", "Paris", "Lisbon"]
    paris = listed[1]
    assert (paris["start"], paris["end"], paris["status"]) == ("2026-11-09", "2026-11-12", "upcoming")
    assert listed[0]["status"] == "completed"


def test_listing_again_does_not_add_trips(tables):
    trips.list_trips(tables[0], ALICE, TODAY)

    assert len(trips.list_trips(tables[0], ALICE, TODAY)) == 3
    assert len(tables[0].entities) == 3


def test_users_see_only_their_own_trips_and_expenses(tables):
    trips.list_trips(tables[0], ALICE, TODAY)
    trips.list_trips(tables[0], BOB, TODAY)
    trips.add_expense(*tables, ALICE, DINNER)

    assert trips.get_trip(*tables, BOB, "TRIP-1001", TODAY)["expenses"] == []
    assert len(trips.get_trip(*tables, ALICE, "TRIP-1001", TODAY)["expenses"]) == 1


def test_a_filed_expense_shows_on_its_trip_with_the_total(tables):
    trips.list_trips(tables[0], ALICE, TODAY)
    filed = trips.add_expense(*tables, ALICE, DINNER, now=datetime(2026, 11, 10, 21, tzinfo=UTC))
    trips.add_expense(*tables, ALICE, {**DINNER, "category": "transport", "amount": 35.5, "attendees": 1})

    trip = trips.get_trip(*tables, ALICE, "TRIP-1001", TODAY)

    assert filed["id"].startswith("EXP-") and filed["currency"] == "EUR"
    assert trip["expenses_total"] == 255.5
    assert trip["expenses"][0]["description"] == "Dinner with the customer"


def test_an_expense_on_someone_elses_trip_is_refused(tables):
    trips.list_trips(tables[0], BOB, TODAY)

    with pytest.raises(trips.InvalidArguments, match="no trip TRIP-1001"):
        trips.add_expense(*tables, ALICE, DINNER)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"trip_id": "1001"}, "trip_id must look like"),
        ({"category": "gift"}, "category must be one of"),
        ({"amount": 0}, "amount must be"),
        ({"amount": 9000}, "amount must be"),
        ({"amount": True}, "amount must be"),
        ({"currency": "euro"}, "currency must be"),
        ({"description": " "}, "description is required"),
        ({"attendees": 0}, "attendees must be"),
    ],
)
def test_invalid_expenses_are_refused_with_a_reason(tables, change, message):
    trips.list_trips(tables[0], ALICE, TODAY)

    with pytest.raises(trips.InvalidArguments, match=message):
        trips.add_expense(*tables, ALICE, {**DINNER, **change})
