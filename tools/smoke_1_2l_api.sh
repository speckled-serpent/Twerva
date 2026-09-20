#!/usr/bin/env bash
# 1.2l-v persist-proof smoke: Brand → SourceItem → Cluster → Account →
# Artifact (draft) → PostJob (scheduled), then GET each.
#
# Usage (API already running, DATABASE_URL applied, schema migrated):
#   tools/smoke_1_2l_api.sh
#   TWERVA_API_BASE_URL=http://127.0.0.1:8000 tools/smoke_1_2l_api.sh
set -euo pipefail

BASE_URL="${TWERVA_API_BASE_URL:-http://127.0.0.1:8000}"
RUN_ID="$(date +%s)"

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

echo "POST /api/v1/source-items"
SOURCE_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/source-items" \
  -H 'Content-Type: application/json' \
  -d "{
    \"brand_id\": \"${BRAND_ID}\",
    \"source_type\": \"spotmu_interest\",
    \"external_key\": \"smoke-${RUN_ID}\",
    \"title\": \"Example Spotmu interest\",
    \"interest_heading\": \"What this example lane is about\",
    \"overview_bullets\": [
      \"A placeholder interest heading for Twerva persist proof.\",
      \"Three overview bullets stand in for a real Spotmu interest.\",
      \"Smoke row — not real ingest.\"
    ],
    \"canonical_url\": \"https://spotmu.com/interest/example\"
  }")"
echo "${SOURCE_BODY}"
SOURCE_ITEM_ID="$(printf '%s' "${SOURCE_BODY}" | json_id)"

echo "POST /api/v1/clusters"
CLUSTER_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/clusters" \
  -H 'Content-Type: application/json' \
  -d "{
    \"brand_id\": \"${BRAND_ID}\",
    \"slug\": \"smoke-lane-${RUN_ID}\",
    \"name\": \"Smoke lane\"
  }")"
echo "${CLUSTER_BODY}"
CLUSTER_ID="$(printf '%s' "${CLUSTER_BODY}" | json_id)"

echo "POST /api/v1/accounts"
ACCOUNT_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/accounts" \
  -H 'Content-Type: application/json' \
  -d "{
    \"cluster_id\": \"${CLUSTER_ID}\",
    \"platform\": \"instagram\",
    \"handle\": \"spotmu_smoke_${RUN_ID}\"
  }")"
echo "${ACCOUNT_BODY}"
ACCOUNT_ID="$(printf '%s' "${ACCOUNT_BODY}" | json_id)"

echo "POST /api/v1/artifacts (status=draft)"
ARTIFACT_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/artifacts" \
  -H 'Content-Type: application/json' \
  -d "{
    \"brand_id\": \"${BRAND_ID}\",
    \"source_item_id\": \"${SOURCE_ITEM_ID}\",
    \"cluster_id\": \"${CLUSTER_ID}\",
    \"status\": \"draft\",
    \"format\": \"carousel\",
    \"caption\": \"Smoke caption\"
  }")"
echo "${ARTIFACT_BODY}"
ARTIFACT_ID="$(printf '%s' "${ARTIFACT_BODY}" | json_id)"
ARTIFACT_STATUS="$(printf '%s' "${ARTIFACT_BODY}" | json_field '"status"')"

if [[ "${ARTIFACT_STATUS}" != "draft" ]]; then
  echo "expected artifact status draft, got ${ARTIFACT_STATUS}" >&2
  exit 1
fi

echo "POST /api/v1/post-jobs (status=scheduled)"
POST_JOB_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/post-jobs" \
  -H 'Content-Type: application/json' \
  -d "{
    \"artifact_id\": \"${ARTIFACT_ID}\",
    \"account_id\": \"${ACCOUNT_ID}\",
    \"status\": \"scheduled\"
  }")"
echo "${POST_JOB_BODY}"
POST_JOB_ID="$(printf '%s' "${POST_JOB_BODY}" | json_id)"
POST_JOB_STATUS="$(printf '%s' "${POST_JOB_BODY}" | json_field '"status"')"

if [[ "${POST_JOB_STATUS}" != "scheduled" ]]; then
  echo "expected post job status scheduled, got ${POST_JOB_STATUS}" >&2
  exit 1
fi

echo "GET each created row"
for path in \
  "/api/v1/brands/${BRAND_ID}" \
  "/api/v1/source-items/${SOURCE_ITEM_ID}" \
  "/api/v1/clusters/${CLUSTER_ID}" \
  "/api/v1/accounts/${ACCOUNT_ID}" \
  "/api/v1/artifacts/${ARTIFACT_ID}" \
  "/api/v1/post-jobs/${POST_JOB_ID}"
do
  echo "GET ${path}"
  GET_BODY="$(curl -sS "${BASE_URL}${path}")"
  echo "${GET_BODY}"
  printf '%s' "${GET_BODY}" | json_id >/dev/null
done

echo "1.2l-v smoke OK  brand=${BRAND_ID} source_item=${SOURCE_ITEM_ID} cluster=${CLUSTER_ID} account=${ACCOUNT_ID} artifact=${ARTIFACT_ID} post_job=${POST_JOB_ID}"
