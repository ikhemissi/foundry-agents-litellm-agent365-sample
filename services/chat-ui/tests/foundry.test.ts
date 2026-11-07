// Foundry mode: the chat calls a Foundry hosted agent as the signed-in user, forwarding the user's tokens, and shows the
// tool calls the agent reports. The event sequence is the one a travel assistant (Agent Framework, Responses protocol)
// streamed live on 2026-11-07 (ids shortened, output cut).
import assert from "node:assert/strict";
import { test } from "node:test";
import { EventType, type BaseEvent } from "@ag-ui/client";
import { createLocalJWKSet, exportJWK, generateKeyPair, SignJWT } from "jose";
import { verifyFoundryToken } from "../lib/server/auth";
import { getConfig, publicConfig, responsesUrl, type FoundryConfig } from "../lib/server/config";
import { foundryToAgUiEvents, streamFoundryAgent } from "../lib/server/foundry";
import type { ResponsesEvent } from "../lib/server/responses-stream";
import { decodeToolResult } from "../lib/tool-result";
import { collect, environment, fromArray, id, streamResponse, type GatewayEvent } from "./helpers";

// The LiteLLM key is not a setting of this mode.
const foundryEnvironment = {
  ...environment,
  LITELLM_API_KEY: undefined,
  CHAT_GATEWAY: "foundry",
  GATEWAY_URL: "https://contoso.services.ai.azure.com/api/projects/travel/",
  FOUNDRY_AGENT: "travel-assistant",
  GATEWAY_SCOPE: `api://${id(3)}/Tools.Use`,
};
const config = getConfig(foundryEnvironment) as FoundryConfig;

const listTrips: GatewayEvent[] = [
  { type: "response.created", response: { id: "resp_1", status: "in_progress" } },
  { type: "response.output_item.added", item: { id: "fc_1", type: "function_call", call_id: "call_1", name: "Contoso_Trips-list_trips", arguments: "", status: "in_progress" } },
  { type: "response.function_call_arguments.done", item_id: "fc_1", arguments: "{}" },
  { type: "response.output_item.done", item: { id: "fc_1", type: "function_call", call_id: "call_1", name: "Contoso_Trips-list_trips", arguments: "{}", status: "completed" } },
  { type: "response.output_item.added", item: { id: "fco_1", type: "function_call_output", call_id: "call_1", output: '{"result": [{"id": "TRIP-1001", "city": "Paris"}]}', status: "in_progress" } },
  { type: "response.output_item.done", item: { id: "fco_1", type: "function_call_output", call_id: "call_1", output: '{"result": [{"id": "TRIP-1001", "city": "Paris"}]}', status: "completed" } },
  { type: "response.output_item.added", item: { id: "msg_1", type: "message", status: "in_progress" } },
  { type: "response.output_text.delta", item_id: "msg_1", delta: "Paris, " },
  { type: "response.output_text.delta", item_id: "msg_1", delta: "next week." },
  { type: "response.output_item.done", item: { id: "msg_1", type: "message", status: "completed" } },
  { type: "response.completed", response: { id: "resp_1", status: "completed" } },
];

const field = (event: BaseEvent | undefined, name: string) => (event as Record<string, unknown> | undefined)?.[name];

test("Foundry mode needs the agent's name and the gateway scope, and gives the browser the Foundry scope", () => {
  assert.equal(responsesUrl(config),
    "https://contoso.services.ai.azure.com/api/projects/travel/agents/travel-assistant/endpoint/protocols/openai/responses?api-version=v1");
  assert.equal(publicConfig(config).foundryScope, "https://ai.azure.com/user_impersonation");
  assert.throws(() => getConfig({ ...foundryEnvironment, GATEWAY_SCOPE: undefined }), /GATEWAY_SCOPE/);
  assert.throws(() => getConfig({ ...foundryEnvironment, FOUNDRY_AGENT: "travel assistant" }), /FOUNDRY_AGENT/);
});

test("the agent is called with the user's Foundry token and both tokens forwarded in x-client-* headers", async () => {
  let sent: RequestInit | undefined;
  const fetchImpl = (async (_url: string, init: RequestInit) => {
    sent = init;
    return streamResponse(listTrips);
  }) as typeof fetch;
  const messages = [{ role: "user" as const, content: "Which trips do I have?" }];

  await collect(streamFoundryAgent({
    config, messages, signal: new AbortController().signal, foundryToken: "foundry-token", gatewayToken: "gateway-token", fetchImpl,
  }));

  const headers = sent?.headers as Record<string, string>;
  assert.equal(headers.Authorization, "Bearer foundry-token");
  assert.equal(headers["x-client-foundry-token"], "foundry-token");
  assert.equal(headers["x-client-gateway-token"], "gateway-token");
  assert.deepEqual(JSON.parse(String(sent?.body)), { input: messages, stream: true });
});

test("a tool call the agent ran is shown once, as soon as it is reported, with its arguments and result", async () => {
  const events = await collect(foundryToAgUiEvents(fromArray(listTrips as ResponsesEvent[]), "run"));

  assert.deepEqual(events.map((event) => event.type), [
    EventType.TOOL_CALL_START, EventType.TOOL_CALL_ARGS, EventType.TOOL_CALL_END, EventType.TOOL_CALL_RESULT,
    EventType.TEXT_MESSAGE_START, EventType.TEXT_MESSAGE_CONTENT, EventType.TEXT_MESSAGE_CONTENT, EventType.TEXT_MESSAGE_END,
  ]);
  const [start, args, , result] = events.slice(0, 4);
  assert.equal(field(start, "toolCallName"), "Contoso_Trips-list_trips");
  assert.equal(field(args, "delta"), "{}");
  assert.equal(field(result, "toolCallId"), "run-call_1");
  assert.match(decodeToolResult(String(field(result, "content"))).output, /TRIP-1001/);
});

test("a stream that ends without response.completed is an error", async () => {
  await assert.rejects(collect(foundryToAgUiEvents(fromArray(listTrips.slice(0, 6) as ResponsesEvent[]), "run")),
    (error: { code: string }) => error.code === "truncated_stream");
});

// Foundry's API issues v1 tokens: issuer sts.windows.net, audience https://ai.azure.com, the client in appid.
const keys = await generateKeyPair("RS256");
const getKey = createLocalJWKSet({ keys: [{ ...(await exportJWK(keys.publicKey)), kid: "test", alg: "RS256" }] });
const signedInUser = { oid: id(5), tid: id(1) };

async function foundryToken(overrides: Record<string, unknown> = {}) {
  const { iss, aud, ...claims } = overrides;
  return new SignJWT({ tid: id(1), oid: id(5), appid: config.UI_CLIENT_ID, scp: "user_impersonation", ...claims })
    .setProtectedHeader({ alg: "RS256", kid: "test" })
    .setIssuer(typeof iss === "string" ? iss : `https://sts.windows.net/${id(1)}/`)
    .setAudience(typeof aud === "string" ? aud : "https://ai.azure.com")
    .setIssuedAt().setExpirationTime("5m").sign(keys.privateKey);
}

test("the signed-in user's delegated Foundry token is accepted and passed on unchanged", async () => {
  const token = await foundryToken();
  assert.equal(await verifyFoundryToken(token, signedInUser, config, getKey), token);
});

for (const [label, overrides, status] of [
  ["a Foundry token for another audience", { aud: id(3) }, 401],
  ["a Foundry token from another issuer", { iss: `https://login.microsoftonline.com/${id(1)}/v2.0` }, 401],
  ["a Foundry token for a different user", { oid: id(6) }, 403],
  ["a Foundry token another app asked for", { appid: id(20) }, 403],
  ["a Foundry token without user_impersonation", { scp: "openid" }, 403],
  ["an application token for Foundry", { idtyp: "app" }, 403],
] as const) {
  test(`refuses ${label} (${status})`, async () => {
    await assert.rejects(verifyFoundryToken(await foundryToken(overrides), signedInUser, config, getKey),
      (error: { status: number }) => error.status === status);
  });
}

test("refuses a missing Foundry token (401)", async () => {
  await assert.rejects(verifyFoundryToken(null, signedInUser, config, getKey), (error: { status: number }) => error.status === 401);
});
