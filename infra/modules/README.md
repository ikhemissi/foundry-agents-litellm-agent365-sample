# Terraform modules

Each module manages one Azure concern and can be copied as-is into another project. It receives the shared resources it uses (resource group, Log Analytics workspace, Container Apps environment, …) as inputs and never creates them. The files in [infra/](..) call the modules and connect them through their outputs.

| Module | What it creates | Virtual network |
|---|---|---|
| [monitoring](monitoring) | Log Analytics workspace, workspace-based Application Insights (Entra-only ingestion) | — |
| [network](network) | Virtual network, the project's subnets (optionally delegated), private DNS zones linked to it | — |
| [container-apps-environment](container-apps-environment) | Container Apps environment (Consumption), logs to Log Analytics | `subnet_id` |
| [container-registry](container-registry) | Container registry without admin credentials, and an AcrPull identity for the apps | private endpoint (Premium) |
| [key-vault](key-vault) | Key Vault with RBAC authorization, and the role to write secrets | private endpoint |
| [postgres](postgres) | PostgreSQL Flexible Server with Entra authentication only, Entra administrator, firewall rules | private endpoint |
| [storage-account](storage-account) | Storage account without shared keys | private endpoint per service |
| [foundry-project](foundry-project) | Microsoft Foundry account (keys disabled), project, chat model deployment, Application Insights connection | private endpoint |
| [container-app](container-app) | Container app for a service that azd deploys, with its own identity and roles; a placeholder image until the first deployment | through its environment |
| [litellm-gateway](litellm-gateway) | LiteLLM proxy (stock image pinned by digest) with an OpenTelemetry collector sidecar, its PostgreSQL database and admin key | through its environment |

Every module that can be reached privately takes the same optional inputs:
- `private_endpoint_subnet_id`: a subnet for private endpoints. `null` (the default) means no private endpoint.
- `private_dns_zone_ids`: the network module's `private_dns_zone_ids` output.

This sample doesn't use a virtual network (see `local.network` in [main.tf](../main.tf)).

## Tests

Each module's `tests/` folder plans it with mock providers, so the tests need no Azure subscription. They check the choices the module makes, including the virtual-network path:

```sh
cd infra/modules/<module> && terraform init -backend=false && terraform test
```
