"""Shared by the experiment scripts: the azd environment, the Azure CLI, Key Vault secrets and LiteLLM's admin API.
Never prints a key."""

import json
import subprocess
import tempfile
import urllib.error
import urllib.request


def azd_values() -> dict[str, str]:
    output = subprocess.run(
        ["azd", "env", "get-values", "--output", "json"], check=True, capture_output=True, text=True
    )
    return json.loads(output.stdout)


def az(*args: str) -> str:
    return subprocess.run(["az", *args, "--output", "tsv"], check=True, capture_output=True, text=True).stdout.strip()


def read_secret(vault: str, name: str) -> str | None:
    try:
        return az("keyvault", "secret", "show", "--vault-name", vault, "--name", name, "--query", "value")
    except subprocess.CalledProcessError:
        return None


def store_secret(vault: str, name: str, value: str) -> None:
    # From a private temporary file, so that the value never appears in a command line.
    with tempfile.NamedTemporaryFile("w", delete=True) as file:
        file.write(value)
        file.flush()
        az("keyvault", "secret", "set", "--vault-name", vault, "--name", name, "--file", file.name, "--query", "id")


class Gateway:
    """LiteLLM's admin and MCP REST API, called with one key."""

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key

    def call(self, method: str, path: str, body: dict | None = None) -> dict | list:
        request = urllib.request.Request(
            self.url + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"{method} {path} failed with {error.code}: {error.read().decode()[:500]}") from None
