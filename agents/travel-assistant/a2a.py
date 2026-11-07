"""A minimal A2A 1.0 client: send one message to an agent over JSON-RPC (`SendMessage`) and read the text of its reply.
The agent is reached through LiteLLM; the caller passes the headers that identify it (its LiteLLM key, the user's
token)."""

import uuid
from typing import Any

import httpx

A2A_VERSION = "1.0"


class A2AError(RuntimeError):
    """The agent answered with an error, or with nothing to read."""


async def send_message(client: httpx.AsyncClient, url: str, text: str, headers: dict[str, str]) -> str:
    message = {"messageId": str(uuid.uuid4()), "role": "ROLE_USER", "parts": [{"text": text}]}
    body = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "SendMessage", "params": {"message": message}}
    response = await client.post(url, json=body, headers={**headers, "A2A-Version": A2A_VERSION})
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise A2AError(f"The agent refused the message: {payload['error'].get('message', 'unknown error')}")
    return reply_text(payload.get("result", {}))


def reply_text(result: dict[str, Any]) -> str:
    """The text of a SendMessage result: a message, or a task whose artifacts (or final status) carry the answer."""
    if "message" in result:
        return _parts_text(result["message"].get("parts", []))
    task = result.get("task", {})
    artifacts_text = "\n".join(_parts_text(artifact.get("parts", [])) for artifact in task.get("artifacts", []))
    text = artifacts_text.strip() or _parts_text(task.get("status", {}).get("message", {}).get("parts", []))
    if not text:
        raise A2AError("The agent's reply had no text.")
    return text


def _parts_text(parts: list[dict[str, Any]]) -> str:
    return "\n".join(part["text"] for part in parts if "text" in part).strip()
