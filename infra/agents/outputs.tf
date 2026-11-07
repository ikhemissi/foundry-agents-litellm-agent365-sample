# Outputs become azd environment values. The azd agents extension finds the Foundry project of the agent services
# (azure.yaml) through AZURE_AI_PROJECT_ID.

output "AZURE_AI_PROJECT_ID" { value = local.project_id }
