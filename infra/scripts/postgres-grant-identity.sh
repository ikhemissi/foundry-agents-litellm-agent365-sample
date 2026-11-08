#!/usr/bin/env bash
# Gives a workload's managed identity a PostgreSQL role and full rights on its own database, so that the workload can
# create and migrate its tables there (e.g. a gateway that manages its own schema). Run by the postprovision hook, as
# the server's Entra administrator. Idempotent.
#   infra/scripts/postgres-grant-identity.sh <role name> <identity principal (object) id> <database>
# The role name of a managed identity is the identity's name; Entra roles can only be created with pgaadauth, in the
# `postgres` database.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROLE="${1:?role name}"
OBJECT_ID="${2:?principal object id}"
DATABASE="${3:?database}"

echo "Granting $ROLE full rights on the database $DATABASE"
"$HERE/psql.sh" -d postgres -q -v role="$ROLE" -v object_id="$OBJECT_ID" -v database="$DATABASE" <<'SQL'
SELECT pgaadauth_create_principal_with_oid(:'role', :'object_id', 'service', false, false)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role');
GRANT ALL PRIVILEGES ON DATABASE :"database" TO :"role";
\connect :"database"
GRANT ALL ON SCHEMA public TO :"role";
SQL
