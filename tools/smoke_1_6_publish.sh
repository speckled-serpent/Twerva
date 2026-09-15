#!/usr/bin/env bash
# 1.6c-iv smoke: seed/generate a draft, approve, schedule, mock-publish.
# Offline from Spotmu and from any live vendor (PUBLISH_ADAPTER=mock).
#
# Usage (API already running, DATABASE_URL applied, schema migrated):
#   tools/smoke_1_6_publish.sh
#   TWERVA_API_BASE_URL=http://127.0.0.1:8000 tools/smoke_1_6_publish.sh
#
# Public nginx on twerva.com stays /health only — use loopback or an SSH
# tunnel for /api/v1.
set -euo pipefail

BASE_URL="${TWERVA_API_BASE_URL:-http://127.0.0.1:8000}"
EXAMPLE_EXTERNAL_KEY="example"
RUN_ID="$(date +%s)"
SCHEDULED_FOR="2026-09-17T15:00:00Z"

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

echo "Find or create SourceItem external_key=${EXAMPLE_EXTERNAL_KEY}"
LIST_SOURCES="$(curl -sS "${BASE_URL}/api/v1/source-items")"
SOURCE_ITEM_ID="$(printf '%s' "${LIST_SOURCES}" | python3 -c '
import json, sys
source_items = json.load(sys.stdin)
for source_item in source_items:
    if source_item.get("external_key") == "example":
        print(source_item["id"])
        break
')"

if [[ -z "${SOURCE_ITEM_ID}" ]]; then
  echo "POST /api/v1/source-items (seed-shaped example, no Spotmu call)"
  SOURCE_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/source-items" \
    -H 'Content-Type: application/json' \
    -d "{
      \"brand_id\": \"${BRAND_ID}\",
      \"source_type\": \"spotmu_interest\",
      \"external_key\": \"${EXAMPLE_EXTERNAL_KEY}\",
      \"title\": \"Example Spotmu interest\",
      \"interest_heading\": \"What this example lane is about\",
      \"overview_bullets\": [
        \"A placeholder interest heading for Twerva persist proof.\",
        \"Three overview bullets stand in for a real Spotmu interest.\",
        \"Seed-shaped smoke row — not a live Spotmu fetch.\"
      ],
      \"canonical_url\": \"https://spotmu.com/interest/example\"
    }")"
  echo "${SOURCE_BODY}"
  SOURCE_ITEM_ID="$(printf '%s' "${SOURCE_BODY}" | json_id)"
else
  echo "Reusing SourceItem ${SOURCE_ITEM_ID}"
fi

echo "POST /api/v1/clusters + account"
CLUSTER_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/clusters" \
  -H 'Content-Type: application/json' \
  -d "{
    \"brand_id\": \"${BRAND_ID}\",
    \"slug\": \"publish-lane-${RUN_ID}\",
    \"name\": \"Publish smoke lane\"
  }")"
echo "${CLUSTER_BODY}"
CLUSTER_ID="$(printf '%s' "${CLUSTER_BODY}" | json_id)"

ACCOUNT_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/accounts" \
  -H 'Content-Type: application/json' \
  -d "{
    \"cluster_id\": \"${CLUSTER_ID}\",
    \"platform\": \"instagram\",
    \"handle\": \"publish_smoke_${RUN_ID}\"
  }")"
echo "${ACCOUNT_BODY}"
ACCOUNT_ID="$(printf '%s' "${ACCOUNT_BODY}" | json_id)"

echo "POST /api/v1/generate/carousel"
GENERATE_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/generate/carousel" \
  -H 'Content-Type: application/json' \
  -d "{\"source_item_id\": \"${SOURCE_ITEM_ID}\", \"cluster_id\": \"${CLUSTER_ID}\"}")"
echo "${GENERATE_BODY}"
ARTIFACT_ID="$(printf '%s' "${GENERATE_BODY}" | json_id)"

echo "POST /api/v1/artifacts/${ARTIFACT_ID}/approve"
APPROVE_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/artifacts/${ARTIFACT_ID}/approve" \
  -H 'Content-Type: application/json' \
  -d '{}')"
echo "${APPROVE_BODY}"
APPROVED_STATUS="$(printf '%s' "${APPROVE_BODY}" | json_field '"status"')"

if [[ "${APPROVED_STATUS}" != "approved" ]]; then
  echo "expected approved, got ${APPROVED_STATUS}" >&2
  exit 1
fi

echo "POST /api/v1/schedule"
SCHEDULE_PAYLOAD="{\"artifact_id\":\"${ARTIFACT_ID}\",\"account_id\":\"${ACCOUNT_ID}\",\"scheduled_for\":\"${SCHEDULED_FOR}\"}"
SCHEDULE_RESPONSE="$(curl -sS -X POST "${BASE_URL}/api/v1/schedule" \
  -H 'Content-Type: application/json' \
  -d "${SCHEDULE_PAYLOAD}")"
echo "${SCHEDULE_RESPONSE}"
POST_JOB_ID="$(printf '%s' "${SCHEDULE_RESPONSE}" | json_id)"
POST_JOB_STATUS="$(printf '%s' "${SCHEDULE_RESPONSE}" | json_field '"status"')"

if [[ "${POST_JOB_STATUS}" != "scheduled" ]]; then
  echo "expected post_job scheduled, got ${POST_JOB_STATUS}" >&2
  exit 1
fi

echo "POST /api/v1/publish/run/${POST_JOB_ID}"
PUBLISH_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/publish/run/${POST_JOB_ID}")"
echo "${PUBLISH_BODY}"
PUBLISH_STATUS="$(printf '%s' "${PUBLISH_BODY}" | json_field '"status"')"
PLATFORM_POST_ID="$(printf '%s' "${PUBLISH_BODY}" | json_field '"platform_post_id"')"
PLATFORM_POST_URL="$(printf '%s' "${PUBLISH_BODY}" | json_field '"platform_post_url"')"
PUBLISHED_AT="$(printf '%s' "${PUBLISH_BODY}" | json_field '"published_at"')"

if [[ "${PUBLISH_STATUS}" != "published" ]]; then
  echo "expected published, got ${PUBLISH_STATUS}" >&2
  exit 1
fi

if [[ "${PLATFORM_POST_ID}" != mock-instagram-* ]]; then
  echo "expected mock-instagram- platform_post_id, got ${PLATFORM_POST_ID}" >&2
  exit 1
fi

if [[ "${PLATFORM_POST_URL}" != https://example.invalid/instagram/p/* ]]; then
  echo "expected example.invalid platform_post_url, got ${PLATFORM_POST_URL}" >&2
  exit 1
fi

if [[ -z "${PUBLISHED_AT}" || "${PUBLISHED_AT}" == "None" || "${PUBLISHED_AT}" == "null" ]]; then
  echo "expected published_at" >&2
  exit 1
fi

echo "GET /api/v1/post-jobs/${POST_JOB_ID}"
GET_JOB="$(curl -sS "${BASE_URL}/api/v1/post-jobs/${POST_JOB_ID}")"
echo "${GET_JOB}"
GET_STATUS="$(printf '%s' "${GET_JOB}" | json_field '"status"')"
GET_PLATFORM_ID="$(printf '%s' "${GET_JOB}" | json_field '"platform_post_id"')"

if [[ "${GET_STATUS}" != "published" ]]; then
  echo "GET expected published, got ${GET_STATUS}" >&2
  exit 1
fi

if [[ "${GET_PLATFORM_ID}" != "${PLATFORM_POST_ID}" ]]; then
  echo "GET platform_post_id mismatch" >&2
  exit 1
fi

echo "Second publish of the same job (expect 409)"
AGAIN_TMP="$(mktemp)"
AGAIN_CODE="$(curl -sS -o "${AGAIN_TMP}" -w '%{http_code}' \
  -X POST "${BASE_URL}/api/v1/publish/run/${POST_JOB_ID}")"
AGAIN_BODY="$(cat "${AGAIN_TMP}")"
rm -f "${AGAIN_TMP}"
echo "republish HTTP ${AGAIN_CODE} ${AGAIN_BODY}"

if [[ "${AGAIN_CODE}" != "409" ]]; then
  echo "expected 409 on already-published job, got ${AGAIN_CODE}" >&2
  exit 1
fi

echo "1.6c-iv smoke OK  source_item=${SOURCE_ITEM_ID} artifact=${ARTIFACT_ID} post_job=${POST_JOB_ID} platform_post_id=${PLATFORM_POST_ID}"
