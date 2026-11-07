# What the agents need from the platform, and the hook that sets them up:
# - the deployer may call the Foundry agents' endpoints (Responses and A2A), with the Foundry Agent Consumer role on
#   the project; give it to other users or a group the same way;
# - hooks/postprovision.sh then configures LiteLLM (src/configure_gateway.py: MCP servers, the A2A agent, one key
#   per agent, the Agent 365 guardrail) and deploys the expense policy agent (src/deploy_policy_agent.py).
# The travel assistant itself is an azd service (azure.yaml); its postdeploy hook gives its identity its roles.

data "azurerm_client_config" "current" {}

locals {
  # https://<account>.services.ai.azure.com/api/projects/<project>
  project_name = reverse(split("/", trimsuffix(var.foundry_project_endpoint, "/")))[0]
  project_id   = "${var.foundry_account_id}/projects/${local.project_name}"
}

resource "azurerm_role_assignment" "deployer_agent_consumer" {
  scope                = local.project_id
  role_definition_name = "Foundry Agent Consumer"
  principal_id         = data.azurerm_client_config.current.object_id
}
