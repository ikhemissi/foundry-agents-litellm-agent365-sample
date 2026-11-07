---
name: expense-policy
description: Check travel expenses against Contoso's travel expense policy, with every limit and figure computed by scripts/policy.py.
license: MIT
compatibility: Requires python3 (standard library only).
---

# Contoso travel expense policy

Contoso's travel expense policy (fictional), in euros, taxes included:

- **Hotels:** a standard room, within the city's nightly limit; above it, the manager approves before booking.
- **Meals:** a limit per person, higher when customers or partners attend (list the attendees); a large meal needs the manager's approval.
- **Transport:** train in standard class for journeys under four hours, economy flights otherwise; taxis when public transport is impractical; a large single expense needs the manager's approval.
- **Other expenses:** above a small amount, the manager approves.
- Keep a receipt above a small amount, and file expenses within 30 days of the end of the trip.

The amounts are in `scripts/policy.py`, not here: never state a limit or compute a figure yourself.

## How to answer

1. Run the script in the code interpreter, once per expense:
   - check an expense: `python {policy_script} check --category meal --amount 220 --count 4 --with-customers`
     (`--category` is hotel, meal, transport or other; `--count` is nights for a hotel, people for a meal;
     add `--city` for a hotel, `--with-customers` when customers or partners attended a meal);
   - the rules and limits of a category: `python {policy_script} rules --category hotel --city Paris`.
2. The script prints one JSON object. If it has an `error`, fix the request as it says, or ask for the missing fact.
3. Answer from that JSON only: within the policy or not, the limit and its basis (`limit_basis`), whether the
   manager's approval and a receipt are needed. Quote the rule from `rules` when it helps.
