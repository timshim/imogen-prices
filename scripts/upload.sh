#!/usr/bin/env bash
# Uploads prices.json to https://imogenpro.com/catalog/prices.json, where Imogen Pro downloads it.
#
# Needs CATALOG_DEPLOY_KEY: the private SSH key of the server's `catalog` user, which can only
# write into the catalog folder (rrsync -wo). The server's host key is pinned below, so the key is
# never offered to a server pretending to be imogenpro.com's.
set -euo pipefail

HOST="catalog@139.162.45.89"
HOST_KEY="139.162.45.89 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKY/JN1mfyfGGfZOY1Kh9U4pZdZ+sEyEachNd24LUISc"
URL="https://imogenpro.com/catalog/prices.json"

if [[ -z "${CATALOG_DEPLOY_KEY:-}" ]]; then
  echo "CATALOG_DEPLOY_KEY isn't set, so prices.json can't be uploaded." >&2
  exit 1
fi

dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT
printf '%s\n' "$CATALOG_DEPLOY_KEY" > "$dir/key"
chmod 600 "$dir/key"
printf '%s\n' "$HOST_KEY" > "$dir/known_hosts"

# rsync writes a temporary file and renames it into place, so the app never downloads half a file.
rsync -tz \
  -e "ssh -i $dir/key -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$dir/known_hosts" \
  prices.json "$HOST:prices.json"

# Check that the site now serves exactly what was uploaded.
curl -fsS --retry 3 "$URL" -o "$dir/served.json"
if ! cmp -s prices.json "$dir/served.json"; then
  echo "$URL doesn't match prices.json after the upload." >&2
  exit 1
fi
echo "Uploaded prices.json to $URL"
