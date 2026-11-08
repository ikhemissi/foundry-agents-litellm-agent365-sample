#!/usr/bin/env bash
# Opens psql on the PostgreSQL server of the current azd environment with YOUR Entra identity (token as password):
#   infra/scripts/psql.sh -d <database> -c "SELECT 1"
#   infra/scripts/psql.sh -d <database> < script.sql
# The host is POSTGRES_HOST from the environment (set inside azd hooks) or from the azd environment. Uses a local psql
# if available, otherwise the postgres:18 image with Podman or Docker. Needs the deployer to be an Entra administrator
# of the server and allowed by its firewall (dev defaults, see infra/postgres.tf).
set -euo pipefail

DATABASE="postgres"
if [[ "${1:-}" == "-d" ]]; then
  DATABASE="$2"
  shift 2
fi
HOST="${POSTGRES_HOST:-$(azd env get-value POSTGRES_HOST 2>/dev/null || true)}"
[[ -n "$HOST" ]] || { echo "POSTGRES_HOST not found: provision first" >&2; exit 1; }
USER_NAME="$(az ad signed-in-user show --query userPrincipalName -o tsv)"
PGPASSWORD="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)"
export PGPASSWORD
CONNECTION="host=$HOST port=5432 dbname=$DATABASE user=$USER_NAME sslmode=require"

if command -v psql >/dev/null; then
  exec psql "$CONNECTION" -v ON_ERROR_STOP=1 "$@"
fi
CLI="${CONTAINER_CLI:-$(command -v podman || command -v docker || true)}"
[[ -n "$CLI" ]] || { echo "psql, podman or docker is required" >&2; exit 1; }
TTY=()
[[ -t 0 && $# -eq 0 ]] && TTY=(-it)
[[ ! -t 0 ]] && TTY=(-i)   # SQL piped on stdin
exec "$CLI" run --rm "${TTY[@]}" -e PGPASSWORD docker.io/library/postgres:18 \
  psql "$CONNECTION" -v ON_ERROR_STOP=1 "$@"
