#!/usr/bin/env bash
# 1.3f-i smoke: ingest one real production Spotmu slug, GET the SourceItem,
# attach it to cluster slug=spotmu-general under Brand spotmu.
#
# Usage (API already running, DATABASE_URL applied, schema migrated):
#   tools/smoke_1_3_ingest.sh
#   TWERVA_API_BASE_URL=http://127.0.0.1:8000 tools/smoke_1_3_ingest.sh
#   SPOTMU_SMOKE_SLUG=ai-agents tools/smoke_1_3_ingest.sh
#
# Talks to production Spotmu (default https://spotmu.com) from the API
# process. Public nginx on twerva.com stays /health only — use loopback
# or an SSH tunnel for /api/v1.
set -euo pipefail

BASE_URL="${TWERVA_API_BASE_URL:-http://127.0.0.1:8000}"
SMOKE_SLUG="${SPOTMU_SMOKE_SLUG:-ai-agents}"
CLUSTER_SLUG="spotmu-general"

json_field() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)['"$1"'])'
}

json_id() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'
}

echo "GET ${BASE_URL}/health"
HEALTH_BODY="$(curl -sS "${BASE_URL}/health")"
echo "${HEALTH_BODY}"
HEALTH_STATUS="$(printf '%s' "${HEALTH_BODY}" | json_field '"status"')"

if [[ "${HEALTH_STATUS}" != "ok" ]]; then
  echo "health failed: ${HEALTH_BODY}" >&2
  exit 1
fi

# shellcheck source=lib/ops_session.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/ops_session.sh"
ops_begin_authenticated_curl "${BASE_URL}"

echo "POST /api/v1/brands (spotmu, or reuse if slug exists)"
BRAND_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/brands" \
  -H 'Content-Type: application/json' \
  -d '{"slug":"spotmu","name":"Spotmu"}')"
echo "${BRAND_BODY}"

if printf '%s' "${BRAND_BODY}" | python3 -c 'import json,sys; json.load(sys.stdin)["id"]' >/dev/null 2>&1; then
  BRAND_ID="$(printf '%s' "${BRAND_BODY}" | json_id)"
else
  LIST_BODY="$(curl -sS "${BASE_URL}/api/v1/brands")"
  BRAND_ID="$(printf '%s' "${LIST_BODY}" | python3 -c '
import json, sys
brands = json.load(sys.stdin)
for brand in brands:
    if brand.get("slug") == "spotmu":
        print(brand["id"])
        break
else:
    raise SystemExit("spotmu brand not found after POST conflict")
')"
fi

echo "POST /api/v1/ingest/spotmu/interests/${SMOKE_SLUG}"
INGEST_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/ingest/spotmu/interests/${SMOKE_SLUG}")"
echo "${INGEST_BODY}"
SOURCE_ITEM_ID="$(printf '%s' "${INGEST_BODY}" | json_id)"
SOURCE_SLUG="$(printf '%s' "${INGEST_BODY}" | json_field '"external_key"')"
SOURCE_TITLE="$(printf '%s' "${INGEST_BODY}" | json_field '"title"')"

if [[ "${SOURCE_SLUG}" != "${SMOKE_SLUG}" ]]; then
  echo "expected external_key ${SMOKE_SLUG}, got ${SOURCE_SLUG}" >&2
  exit 1
fi

echo "GET /api/v1/source-items/${SOURCE_ITEM_ID}"
GET_SOURCE_BODY="$(curl -sS "${BASE_URL}/api/v1/source-items/${SOURCE_ITEM_ID}")"
echo "${GET_SOURCE_BODY}"
printf '%s' "${GET_SOURCE_BODY}" | json_id >/dev/null

echo "POST /api/v1/clusters (slug=${CLUSTER_SLUG}, or reuse)"
CLUSTER_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/clusters" \
  -H 'Content-Type: application/json' \
  -d "{
    \"brand_id\": \"${BRAND_ID}\",
    \"slug\": \"${CLUSTER_SLUG}\",
    \"name\": \"Spotmu general\"
  }")"
echo "${CLUSTER_BODY}"

if printf '%s' "${CLUSTER_BODY}" | python3 -c 'import json,sys; json.load(sys.stdin)["id"]' >/dev/null 2>&1; then
  CLUSTER_ID="$(printf '%s' "${CLUSTER_BODY}" | json_id)"
else
  LIST_CLUSTERS="$(curl -sS "${BASE_URL}/api/v1/clusters")"
  CLUSTER_ID="$(printf '%s' "${LIST_CLUSTERS}" | python3 -c '
import json, sys
clusters = json.load(sys.stdin)
for cluster in clusters:
    if cluster.get("slug") == "spotmu-general":
        print(cluster["id"])
        break
else:
    raise SystemExit("spotmu-general cluster not found after POST conflict")
')"
fi

echo "POST /api/v1/clusters/${CLUSTER_ID}/source-items/${SOURCE_ITEM_ID}"
ATTACH_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}/source-items/${SOURCE_ITEM_ID}")"
echo "${ATTACH_BODY}"
ATTACHED_IDS="$(printf '%s' "${ATTACH_BODY}" | python3 -c '
import json, sys
cluster = json.load(sys.stdin)
print(" ".join(cluster.get("source_item_ids") or []))
')"

if [[ "${ATTACHED_IDS}" != *"${SOURCE_ITEM_ID}"* ]]; then
  echo "expected source_item_ids to include ${SOURCE_ITEM_ID}, got ${ATTACHED_IDS}" >&2
  exit 1
fi

echo "GET /api/v1/clusters/${CLUSTER_ID}"
GET_CLUSTER_BODY="$(curl -sS "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}")"
echo "${GET_CLUSTER_BODY}"

echo "1.3f-i smoke OK  slug=${SMOKE_SLUG} title=${SOURCE_TITLE} source_item=${SOURCE_ITEM_ID} cluster=${CLUSTER_ID} brand=${BRAND_ID}"
