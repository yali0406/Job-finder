#!/usr/bin/env bash
# Deploys the site (docs/) and its API (functions/) to Cloudflare Pages.
# On the first run it creates the D1 database; every run applies new migrations.
# Needs CLOUDFLARE_API_TOKEN (Pages + D1 edit), CLOUDFLARE_ACCOUNT_ID, GOOGLE_CLIENT_ID,
# GOOGLE_CLIENT_SECRET and ADMIN_EMAIL in the environment.
set -euo pipefail
cd "$(dirname "$0")/.."
W="npx --yes wrangler@4"
DB=job-finder
PROJECT=job-finder

db_id() { $W d1 list --json | python3 -c "import json,sys; print(next((d['uuid'] for d in json.load(sys.stdin) if d['name']=='$DB'), ''))"; }
id=$(db_id)
if [ -z "$id" ]; then
  $W d1 create "$DB" >/dev/null
  id=$(db_id)
fi
sed -i "s/^database_id = .*/database_id = \"$id\"/; s/^GOOGLE_CLIENT_ID = .*/GOOGLE_CLIENT_ID = \"$GOOGLE_CLIENT_ID\"/" wrangler.toml

$W d1 migrations apply "$DB" --remote
printf %s "$GOOGLE_CLIENT_SECRET" | $W pages secret put GOOGLE_CLIENT_SECRET --project-name "$PROJECT" >/dev/null
printf %s "$ADMIN_EMAIL" | $W pages secret put ADMIN_EMAIL --project-name "$PROJECT" >/dev/null
$W pages deploy --project-name "$PROJECT" --branch main
