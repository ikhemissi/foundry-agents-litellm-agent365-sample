// Foundry mode: calls a Foundry hosted agent's Responses endpoint as the signed-in user, and turns its stream into
// AG-UI events. The agent runs its tools itself; it acts for the user with the two tokens forwarded to it in x-client-*
// headers, which Foundry passes on to the agent's container: the user's gateway token (MCP servers through the
// gateway) and Foundry token (other Foundry agents, over A2A through the gateway). This server never calls the gateway.
import { EventType, type BaseEvent } from "@ag-ui/client";
import { encodeToolResult } from "../tool-result";
import { responsesUrl, type FoundryConfig } from "./config";
import { ChatError } from "./errors";
import { streamResponses, type ChatMessage, type ResponsesEvent } from "./responses-stream";
import { failureMessage, textEvent, toolOutcome } from "./responses-to-ag-ui";

export function streamFoundryAgent({
  config, messages, signal, foundryToken, gatewayToken, fetchImpl,
}: {
  config: FoundryConfig; messages: ChatMessage[]; signal: AbortSignal; foundryToken: string; gatewayToken: string;
  fetchImpl?: typeof fetch;
}): AsyncGenerator<ResponsesEvent> {
  const headers = {
    Authorization: `Bearer ${foundryToken}`,
    "x-client-foundry-token": foundryToken,
    "x-client-gateway-token": gatewayToken,
    "Content-Type": "application/json",
  };
  return streamResponses({
    url: responsesUrl(config), model: config.CHAT_MODEL, headers, signal, fetchImpl,
    body: { input: messages, stream: true },
  });
}

// The agent reports each tool call as a function_call item (its name and arguments), then a function_call_output item
// with the same call_id (its result). Unlike the gateway modes, tool calls are shown as soon as the agent reports them:
// a hosted agent can take several seconds per tool (another agent over A2A), and the user sees its progress.
export async function* foundryToAgUiEvents(
  events: AsyncIterable<ResponsesEvent>, idPrefix: string,
): AsyncGenerator<BaseEvent> {
  const id = (callId: string) => `${idPrefix}-${callId}`;
  for await (const event of events) {
    const text = textEvent(event, idPrefix);
    if (text) {
      yield text;
      continue;
    }
    const item = event.item;
    if (event.type === "response.output_item.done" && item?.type === "function_call" && item.call_id) {
      const toolCallId = id(item.call_id);
      yield { type: EventType.TOOL_CALL_START, toolCallId, toolCallName: item.name ?? "unknown tool" };
      yield { type: EventType.TOOL_CALL_ARGS, toolCallId, delta: item.arguments || "{}" };
      yield { type: EventType.TOOL_CALL_END, toolCallId };
      continue;
    }
    if (event.type === "response.output_item.done" && item?.type === "function_call_output" && item.call_id) {
      yield {
        type: EventType.TOOL_CALL_RESULT, role: "tool", messageId: id(`${item.call_id}-result`),
        toolCallId: id(item.call_id), content: encodeToolResult(toolOutcome(item)),
      } as BaseEvent;
      continue;
    }
    switch (event.type) {
      case "response.completed":
        if (event.response?.status !== "completed") throw new ChatError("gateway", "response_failed", failureMessage(event));
        return;
      case "response.failed":
      case "response.incomplete":
      case "error":
        throw new ChatError("gateway", "response_failed", failureMessage(event));
    }
  }
  throw new ChatError("gateway", "truncated_stream", "The agent closed the stream before the response was complete.");
}
