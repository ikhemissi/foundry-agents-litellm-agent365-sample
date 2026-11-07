"""The A2A 1.0 client: what it sends, and how it reads the answer of a message or a task."""

import json

import a2a
import httpx
import pytest

URL = "https://gateway.example/a2a/expense-policy"


def answering(payload, seen):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_a_message_is_sent_as_a_json_rpc_send_message_with_the_a2a_1_0_header():
    seen = []
    reply = {"jsonrpc": "2.0", "id": "1", "result": {"message": {"role": "ROLE_AGENT", "parts": [{"text": "Yes."}]}}}

    async with answering(reply, seen) as client:
        answer = await a2a.send_message(client, URL, "Is a 220 EUR dinner fine?", {"Authorization": "Bearer user"})

    body = json.loads(seen[0].content)
    assert answer == "Yes."
    assert (body["method"], body["params"]["message"]["role"]) == ("SendMessage", "ROLE_USER")
    assert body["params"]["message"]["parts"] == [{"text": "Is a 220 EUR dinner fine?"}]
    assert (seen[0].headers["A2A-Version"], seen[0].headers["Authorization"]) == ("1.0", "Bearer user")


def test_a_task_answer_is_read_from_its_artifacts():
    task = {
        "task": {
            "artifacts": [{"parts": [{"text": "Within the limit"}, {"data": {}}]}, {"parts": [{"text": "(360 EUR)"}]}]
        }
    }

    assert a2a.reply_text(task) == "Within the limit\n(360 EUR)"


def test_a_task_without_artifacts_is_read_from_its_final_status():
    task = {"task": {"status": {"state": "TASK_STATE_COMPLETED", "message": {"parts": [{"text": "Done"}]}}}}

    assert a2a.reply_text(task) == "Done"


def test_an_empty_reply_is_an_error():
    with pytest.raises(a2a.A2AError, match="no text"):
        a2a.reply_text({"task": {"artifacts": []}})


async def test_a_json_rpc_error_is_raised_with_its_message():
    reply = {"jsonrpc": "2.0", "id": "1", "error": {"code": -32001, "message": "Access to agent is blocked"}}

    async with answering(reply, []) as client:
        with pytest.raises(a2a.A2AError, match="Access to agent is blocked"):
            await a2a.send_message(client, URL, "Hello", {})
