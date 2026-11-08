"""Deploys Contoso's expense policy agent, a Foundry prompt agent, with the stable Foundry REST API (api-version v1).
Idempotent; reads the azd environment and uses your Azure CLI sign-in. Never prints a key. Run by the postprovision
hook, after src/configure_gateway.py (which creates the agent's LiteLLM key), or:
    uv run python src/deploy_policy_agent.py

1. A project connection, litellm (ModelGateway), holds the agent's own LiteLLM key, so that it never appears in the
   agent's definition; the agent's model is litellm/<model>.
2. The policy's code (agents/expense-policy/skill/scripts/policy.py), uploaded as a project file named after its
   content's hash: uploaded again only when it changed. Earlier uploads stay, for the agent's earlier versions.
3. The agent: its role (agents/expense-policy/agent.json), then the expense-policy skill
   (agents/expense-policy/skill/SKILL.md, in the open Agent Skills format) as instructions, and the code interpreter
   with the policy's code, so that every figure it states is computed by that code. A new version only when this
   definition changed.
4. Its endpoint: Responses and A2A, for Entra callers (the user's Foundry token, which LiteLLM passes on). Callers
   need the Foundry Agent Consumer role on the project (infra/agents.tf gives it to the deployer).
"""

import hashlib
import json
import os
import subprocess
import tempfile
import urllib.request
import uuid
from pathlib import Path

from configure_gateway import POLICY_AGENT_KEY_SECRET, POLICY_FOUNDRY_AGENT
from gateway_admin import azd_values, read_secret

ARM_API = "2025-04-01-preview"
FOUNDRY_API = "v1"
MODEL_CONNECTION = "litellm"
AGENT_FOLDER = Path(__file__).parent.parent / "agents" / "expense-policy"
DEFINITION_FILE = AGENT_FOLDER / "agent.json"
SKILL_FILE = AGENT_FOLDER / "skill" / "SKILL.md"
POLICY_SCRIPT = AGENT_FOLDER / "skill" / "scripts" / "policy.py"


def az_rest(method: str, url: str, resource: str, body: dict | None = None) -> dict:
    """Calls an Azure REST API with your Azure CLI sign-in; the body goes through a private temporary file, so that
    keys never appear in a command line."""
    command = ["az", "rest", "--method", method, "--url", url, "--resource", resource, "--output", "json"]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=True) as file:
        if body is not None:
            json.dump(body, file)
            file.flush()
            command += ["--body", f"@{file.name}", "--headers", f"Content-Type={content_type(method)}"]
        output = subprocess.run(command, check=True, capture_output=True, text=True).stdout
    return json.loads(output) if output.strip() else {}


def content_type(method: str) -> str:
    return "application/merge-patch+json" if method == "PATCH" else "application/json"


def ensure_model_connection(values: dict, key: str) -> None:
    project_name = values["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/").rsplit("/", 1)[1]
    base = f"https://management.azure.com{values['FOUNDRY_ACCOUNT_ID']}/projects/{project_name}/connections"
    model = values["FOUNDRY_MODEL_DEPLOYMENT_NAME"]
    model_connection = {
        "category": "ModelGateway",
        "target": f"{values['LITELLM_URL']}/v1",
        "authType": "ApiKey",
        "isSharedToAll": False,
        "credentials": {"key": key},
        "metadata": {
            "deploymentInPath": "false",
            "inferenceAPIVersion": "",
            # LiteLLM reads its keys from a bearer Authorization header.
            "authConfig": json.dumps({"type": "api_key", "name": "Authorization", "format": "Bearer {api_key}"}),
            "models": json.dumps(
                [{"name": model, "properties": {"model": {"name": model, "version": "", "format": "OpenAI"}}}]
            ),
        },
    }
    url = f"{base}/{MODEL_CONNECTION}?api-version={ARM_API}"
    az_rest("PUT", url, "https://management.azure.com", {"properties": model_connection})
    print(f"Connection '{MODEL_CONNECTION}' set (ModelGateway)")


def ensure_policy_file(values: dict) -> dict:
    """The policy's code as a project file (purpose assistants), found by its name: policy-<content hash>.py."""
    content = POLICY_SCRIPT.read_bytes()
    filename = f"policy-{hashlib.sha256(content).hexdigest()[:12]}.py"
    files_url = f"{values['FOUNDRY_PROJECT_ENDPOINT']}/openai/v1/files"
    listed = az_rest("GET", files_url, "https://ai.azure.com").get("data", [])
    existing = [file for file in listed if file.get("filename") == filename]
    if existing:
        print(f"Policy code unchanged ({filename})")
        return existing[0]
    uploaded = upload_file(files_url, filename, content)
    print(f"Policy code uploaded ({filename})")
    return uploaded


def upload_file(files_url: str, filename: str, content: bytes) -> dict:
    """A multipart upload, which az rest does not do; the token comes from your Azure CLI sign-in."""
    command = ["az", "account", "get-access-token", "--resource", "https://ai.azure.com", "--query", "accessToken"]
    token = subprocess.run([*command, "--output", "tsv"], check=True, capture_output=True, text=True).stdout.strip()
    boundary = uuid.uuid4().hex
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nassistants\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: text/x-python\r\n\r\n"
        ).encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": f"multipart/form-data; boundary={boundary}"}
    request = urllib.request.Request(files_url, method="POST", data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())


def skill_instructions(policy_file: dict) -> str:
    """SKILL.md without its front matter, pointing at the policy's code where the code interpreter finds it:
    /mnt/data/<file id>-<file name>."""
    body = SKILL_FILE.read_text().split("---", 2)[2].strip()
    return body.replace("{policy_script}", f"/mnt/data/{policy_file['id']}-{policy_file['filename']}")


def desired_definition(values: dict, policy_file: dict) -> dict:
    agent = json.loads(DEFINITION_FILE.read_text())
    return {
        "kind": "prompt",
        "model": f"{MODEL_CONNECTION}/{values['FOUNDRY_MODEL_DEPLOYMENT_NAME']}",
        "instructions": f"{agent['instructions']}\n\n{skill_instructions(policy_file)}",
        "tools": [{"type": "code_interpreter", "container": {"type": "auto", "file_ids": [policy_file["id"]]}}],
    }


def ensure_agent(values: dict, policy_file: dict) -> None:
    agent_url = f"{values['FOUNDRY_PROJECT_ENDPOINT']}/agents/{POLICY_FOUNDRY_AGENT}"
    description = json.loads(DEFINITION_FILE.read_text())["description"]
    definition = desired_definition(values, policy_file)
    try:
        latest = az_rest("GET", f"{agent_url}?api-version={FOUNDRY_API}", "https://ai.azure.com")["versions"]["latest"]
    except subprocess.CalledProcessError:
        latest = None  # not deployed yet
    unchanged = (
        latest
        and latest.get("description") == description
        and all(latest["definition"].get(field) == value for field, value in definition.items())
    )
    if unchanged:
        print(f"Agent '{POLICY_FOUNDRY_AGENT}' unchanged (version {latest['version']})")
        return
    body = {"description": description, "definition": definition}
    created = az_rest("POST", f"{agent_url}/versions?api-version={FOUNDRY_API}", "https://ai.azure.com", body)
    print(f"Agent '{POLICY_FOUNDRY_AGENT}' deployed (version {created['version']})")


def enable_a2a(values: dict) -> None:
    agent_url = f"{values['FOUNDRY_PROJECT_ENDPOINT']}/agents/{POLICY_FOUNDRY_AGENT}?api-version={FOUNDRY_API}"
    endpoint = {
        "agent_endpoint": {"protocols": ["responses", "a2a"], "authorization_schemes": [{"type": "Entra"}]},
        "agent_card": {
            "description": "Answers questions about Contoso's travel expense policy.",
            "skills": [
                {
                    "id": "expense-policy",
                    "name": "Expense policy",
                    "description": "Limits, approvals and receipts for travel expenses.",
                }
            ],
        },
    }
    az_rest("PATCH", agent_url, "https://ai.azure.com", endpoint)
    print(f"Agent '{POLICY_FOUNDRY_AGENT}': Responses and A2A endpoint enabled for Entra callers")


def main() -> None:
    values = {**azd_values(), **os.environ}
    key = read_secret(values["KEY_VAULT_NAME"], POLICY_AGENT_KEY_SECRET)
    if not key:
        raise SystemExit("The expense policy agent's LiteLLM key is missing: run src/configure_gateway.py first.")
    ensure_model_connection(values, key)
    ensure_agent(values, ensure_policy_file(values))
    enable_a2a(values)


if __name__ == "__main__":
    main()
