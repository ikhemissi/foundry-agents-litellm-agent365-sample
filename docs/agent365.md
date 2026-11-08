# Govern the sample with Agent 365

Agent 365 governs the MCP servers LiteLLM exposes: it discovers them and their tools, blocks and unblocks a whole server or a single tool, and (through LiteLLM's `agent_365` guardrail) evaluates every tool call as the signed-in user before it runs.

## Connect LiteLLM

Agent 365 connects to LiteLLM with a dedicated proxy-admin key, which `src/configure_gateway.py` creates so that it can be revoked without touching LiteLLM's master key:

```bash
azd env get-value LITELLM_URL
az keyvault secret show --vault-name "$(azd env get-value KEY_VAULT_NAME)" -n agent365-gateway-key --query value -o tsv
```

In the Microsoft 365 admin center, open the Agent 365 gateway settings, add a LiteLLM gateway with that URL and key, and wait for its MCP server to appear in the tools: `Contoso_Trips`, with `list_trips`, `get_trip` and `add_expense`. Agent 365 lists the tools with its key only; the trips server answers discovery without a user token.

## Block and unblock a tool

1. In the chat, ask: *"Please file a 35 EUR taxi on my Paris trip."* The travel assistant checks the policy, then files it with `Contoso_Trips-add_expense`.
2. In Agent 365, block the tool `add_expense` of `Contoso_Trips`.
3. Ask to file another expense (for example *"Please file a 40 EUR taxi fare on my Paris trip."*). LiteLLM no longer lists `add_expense`, so the travel assistant does not have it: it still checks the policy, then answers that expense filing isn't available. Reading trips (`list_trips`, `get_trip`) still works.
4. Unblock `add_expense` and ask again: the expense is filed.

Observed on 2026-11-07: a block or an unblock took effect within seconds. Blocking the whole server stops every trips tool the same way; Agent 365 applies a block as LiteLLM's allowlist for the server, so it holds for every key and every caller.

`src/configure_gateway.py` registers `Contoso_Trips` under an enforced tool allowlist of its three tools, which per-tool toggles need; when it runs again, it keeps the server's current allowlist, so it never undoes a block made in Agent 365.

## See the evaluations

With the guardrail on, Agent 365 evaluates each tool call as the user before LiteLLM runs it; a call without a user token is refused.

- In Application Insights, each evaluation is a `guardrail` dependency with its verdict (for example `Allow`, `defender_status: Evaluated`) and Agent 365's latency.
- In Microsoft Defender XDR (Advanced Hunting), each call is a `CloudAppEvents` record naming the user, the tool and the server.

```kusto
// Application Insights: the guardrail's verdicts, last hour
dependencies
| where timestamp > ago(1h) and name == "guardrail"
| extend verdict = tostring(parse_json(tostring(customDimensions.guardrail_response)).verdict)
| project timestamp, verdict, duration
| order by timestamp desc
```
