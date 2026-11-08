"""Asks the travel assistant a question as you, without the chat UI: what the chat UI does for each message.
Your tokens come from your Azure CLI sign-in (the Azure CLI is pre-authorized on the gateway app):
- a Foundry token (https://ai.azure.com): to call the hosted agent, and forwarded for the expense policy agent (A2A);
- a gateway token (the gateway app's Tools.Use scope): forwarded for the trips MCP server, through LiteLLM.
    uv run python src/ask_travel_assistant.py "What are my upcoming trips?"
Prints the answer, then the tool calls the agent made, and the time it took."""

import json
import subprocess
import sys
import time
import urllib.request

from gateway_admin import azd_values

AGENT = "travel-assistant"


def access_token(*scope_args: str) -> str:
    command = ["az", "account", "get-access-token", *scope_args, "--query", "accessToken", "--output", "tsv"]
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout.strip()


def ask(question: str) -> dict:
    values = azd_values()
    foundry_token = access_token("--resource", "https://ai.azure.com")
    gateway_token = access_token("--scope", values["GATEWAY_SCOPE"])
    url = f"{values['FOUNDRY_PROJECT_ENDPOINT']}/agents/{AGENT}/endpoint/protocols/openai/responses?api-version=v1"
    request = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps({"input": question, "stream": False}).encode(),
        headers={
            "Authorization": f"Bearer {foundry_token}",
            "x-client-foundry-token": foundry_token,
            "x-client-gateway-token": gateway_token,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read())


def main() -> None:
    question = " ".join(sys.argv[1:]) or "What are my upcoming trips?"
    started = time.monotonic()
    response = ask(question)
    elapsed = time.monotonic() - started
    for item in response.get("output", []):
        if item.get("type") == "message":
            print("".join(part.get("text", "") for part in item.get("content", [])))
    calls = [item for item in response.get("output", []) if item.get("type") not in ("message", "reasoning")]
    for call in calls:
        print(f"- {call.get('type')}: {call.get('name', '')} {call.get('arguments', '')}"[:200])
    print(f"({elapsed:.1f} s)")


if __name__ == "__main__":
    main()
