# Outputs become azd environment values. The azd agents extension finds the Foundry project of the agent services
# (azure.yaml) through AZURE_AI_PROJECT_ID.

output "AZURE_AI_PROJECT_ID" { value = local.project_id }

# The chat UI (infra/chat-ui) talks to the travel assistant, as the signed-in user.
output "CHAT_UI_FOUNDRY_AGENT" { value = "travel-assistant" }
output "CHAT_UI_TITLE" { value = "Contoso travel assistant" }
output "CHAT_UI_INTRO" {
  value = "A Foundry hosted agent that acts for you: it reads your trips and files expenses through LiteLLM (MCP, governed by Agent 365), and asks Contoso's expense policy agent over A2A 1.0. Each tool call is shown under the answer."
}
