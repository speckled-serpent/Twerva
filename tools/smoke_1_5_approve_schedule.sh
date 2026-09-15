#!/usr/bin/env bash
# 1.5c-iii smoke: seed/generate a draft, review-queue approve, schedule a
# post_job. Cadence cap 409 on a second same-UTC-day schedule. Offline
# from Spotmu (DB source + generate only).
#
# Usage (API already running, DATABASE_URL applied, schema migrated):
#   tools/smoke_1_5_approve_schedule.sh
#   TWERVA_API_BASE_URL=http://127.0.0.1:8000 tools/smoke_1_5_approve_schedule.sh
#
# Public nginx on twerva.com stays /health only — use loopback or an SSH
# tunnel for /api/v1.
set -euo pipefail

BASE_URL="${TWERVA_API_BASE_URL:-http://127.0.0.1:8000}"
EXAMPLE_EXTERNAL_KEY="example"
RUN_ID="$(date +%s)"
SCHEDULED_FOR="2026-09-16T15:00:00Z"

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

echo "POST /api/v1/clusters + account (cadence_cap_per_day=1)"
CLUSTER_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/clusters" \
  -H 'Content-Type: application/json' \
  -d "{
    \"brand_id\": \"${BRAND_ID}\",
    \"slug\": \"approve-lane-${RUN_ID}\",
    \"name\": \"Approve smoke lane\"
  }")"
echo "${CLUSTER_BODY}"
CLUSTER_ID="$(printf '%s' "${CLUSTER_BODY}" | json_id)"

ACCOUNT_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/accounts" \
  -H 'Content-Type: application/json' \
  -d "{
    \"cluster_id\": \"${CLUSTER_ID}\",
    \"platform\": \"instagram\",
    \"handle\": \"approve_smoke_${RUN_ID}\",
    \"cadence_cap_per_day\": 1
  }")"
echo "${ACCOUNT_BODY}"
ACCOUNT_ID="$(printf '%s' "${ACCOUNT_BODY}" | json_id)"

echo "POST /api/v1/generate/carousel"
GENERATE_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/generate/carousel" \
  -H 'Content-Type: application/json' \
  -d "{\"source_item_id\": \"${SOURCE_ITEM_ID}\", \"cluster_id\": \"${CLUSTER_ID}\"}")"
echo "${GENERATE_BODY}"
ARTIFACT_ID="$(printf '%s' "${GENERATE_BODY}" | json_id)"
ARTIFACT_STATUS="$(printf '%s' "${GENERATE_BODY}" | json_field '"status"')"

if [[ "${ARTIFACT_STATUS}" != "draft" ]]; then
  echo "expected artifact status draft, got ${ARTIFACT_STATUS}" >&2
  exit 1
fi

echo "GET /api/v1/artifacts?status=draft"
DRAFT_LIST="$(curl -sS "${BASE_URL}/api/v1/artifacts?status=draft")"
printf '%s' "${DRAFT_LIST}" | python3 -c '
import json, sys
artifact_id = sys.argv[1]
drafts = json.load(sys.stdin)
ids = {artifact["id"] for artifact in drafts}
if artifact_id not in ids:
    raise SystemExit(f"draft queue missing artifact {artifact_id}")
print(f"draft queue size={len(drafts)}")
' "${ARTIFACT_ID}"

echo "PATCH /api/v1/artifacts/${ARTIFACT_ID} caption"
PATCH_BODY="$(curl -sS -X PATCH "${BASE_URL}/api/v1/artifacts/${ARTIFACT_ID}" \
  -H 'Content-Type: application/json' \
  -d '{"caption":"smoke patched caption"}')"
echo "${PATCH_BODY}"
PATCHED_CAPTION="$(printf '%s' "${PATCH_BODY}" | json_field '"caption"')"

if [[ "${PATCHED_CAPTION}" != "smoke patched caption" ]]; then
  echo "expected patched caption, got ${PATCHED_CAPTION}" >&2
  exit 1
fi

echo "POST /api/v1/artifacts/${ARTIFACT_ID}/approve"
APPROVE_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/artifacts/${ARTIFACT_ID}/approve" \
  -H 'Content-Type: application/json' \
  -d '{"caption":"smoke approved caption"}')"
echo "${APPROVE_BODY}"
APPROVED_STATUS="$(printf '%s' "${APPROVE_BODY}" | json_field '"status"')"
APPROVED_CAPTION="$(printf '%s' "${APPROVE_BODY}" | json_field '"caption"')"
APPROVED_AT="$(printf '%s' "${APPROVE_BODY}" | json_field '"approved_at"')"

if [[ "${APPROVED_STATUS}" != "approved" ]]; then
  echo "expected approved, got ${APPROVED_STATUS}" >&2
  exit 1
fi

if [[ "${APPROVED_CAPTION}" != "smoke approved caption" ]]; then
  echo "expected approve caption, got ${APPROVED_CAPTION}" >&2
  exit 1
fi

if [[ -z "${APPROVED_AT}" || "${APPROVED_AT}" == "None" ]]; then
  echo "expected approved_at" >&2
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

echo "GET /api/v1/post-jobs/${POST_JOB_ID}"
GET_JOB="$(curl -sS "${BASE_URL}/api/v1/post-jobs/${POST_JOB_ID}")"
echo "${GET_JOB}"
GET_JOB_ID="$(printf '%s' "${GET_JOB}" | json_id)"

if [[ "${GET_JOB_ID}" != "${POST_JOB_ID}" ]]; then
  echo "GET post_job id mismatch" >&2
  exit 1
fi

echo "Second generate + approve + schedule same UTC day (expect 409)"
SECOND_GENERATE="$(curl -sS -X POST "${BASE_URL}/api/v1/generate/carousel" \
  -H 'Content-Type: application/json' \
  -d "{\"source_item_id\": \"${SOURCE_ITEM_ID}\", \"cluster_id\": \"${CLUSTER_ID}\"}")"
SECOND_ARTIFACT_ID="$(printf '%s' "${SECOND_GENERATE}" | json_id)"
curl -sS -X POST "${BASE_URL}/api/v1/artifacts/${SECOND_ARTIFACT_ID}/approve" \
  -H 'Content-Type: application/json' \
  -d '{}' >/dev/null
SECOND_PAYLOAD="{\"artifact_id\":\"${SECOND_ARTIFACT_ID}\",\"account_id\":\"${ACCOUNT_ID}\",\"scheduled_for\":\"${SCHEDULED_FOR}\"}"
CAP_TMP="$(mktemp)"
CAP_CODE="$(curl -sS -o "${CAP_TMP}" -w '%{http_code}' -X POST "${BASE_URL}/api/v1/schedule" \
  -H 'Content-Type: application/json' \
  -d "${SECOND_PAYLOAD}")"
CAP_BODY="$(cat "${CAP_TMP}")"
rm -f "${CAP_TMP}"
echo "schedule cap HTTP ${CAP_CODE} ${CAP_BODY}"

if [[ "${CAP_CODE}" != "409" ]]; then
  echo "expected 409 cadence cap, got ${CAP_CODE}" >&2
  exit 1
fi

echo "Reject a third draft; re-approve must 409"
THIRD_GENERATE="$(curl -sS -X POST "${BASE_URL}/api/v1/generate/carousel" \
  -H 'Content-Type: application/json' \
  -d "{\"source_item_id\": \"${SOURCE_ITEM_ID}\"}")"
THIRD_ARTIFACT_ID="$(printf '%s' "${THIRD_GENERATE}" | json_id)"
curl -sS -X POST "${BASE_URL}/api/v1/artifacts/${THIRD_ARTIFACT_ID}/reject" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"smoke reject"}' >/dev/null
REJECT_TMP="$(mktemp)"
REJECT_CODE="$(curl -sS -o "${REJECT_TMP}" -w '%{http_code}' \
  -X POST "${BASE_URL}/api/v1/artifacts/${THIRD_ARTIFACT_ID}/approve")"
rm -f "${REJECT_TMP}"

if [[ "${REJECT_CODE}" != "409" ]]; then
  echo "expected 409 re-approve after reject, got ${REJECT_CODE}" >&2
  exit 1
fi

echo "1.5c-iii smoke OK  source_item=${SOURCE_ITEM_ID} artifact=${ARTIFACT_ID} post_job=${POST_JOB_ID} brand=${BRAND_ID} account=${ACCOUNT_ID}"
