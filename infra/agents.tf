# The two Foundry agents. The travel assistant is an azd service (azure.yaml): azd deploys it, and its postdeploy hook
# gives its identity its roles (scripts/grant-travel-assistant.sh), since that identity exists only once it is
# deployed. The expense policy agent is deployed by the postprovision hook (src/deploy_policy_agent.py).

# The deployer may call the agents' endpoints (Responses and A2A); give other users or a group the same role.
resource "azurerm_role_assignment" "deployer_agent_consumer" {
  scope                = module.foundry.project_id
  role_definition_name = "Foundry Agent Consumer"
  principal_id         = data.azurerm_client_config.current.object_id
}
