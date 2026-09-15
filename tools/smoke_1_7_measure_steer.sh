#!/usr/bin/env bash
# 1.7d-ii smoke: mock-publish jobs, POST metrics, cluster median, steer, summary.
# Offline from Spotmu and from any live analytics vendor.
#
# Usage (API already running, DATABASE_URL applied, schema migrated):
#   tools/smoke_1_7_measure_steer.sh
#   TWERVA_API_BASE_URL=http://127.0.0.1:8000 tools/smoke_1_7_measure_steer.sh
#
# Public nginx on twerva.com stays /health only — use loopback or an SSH
# tunnel for /api/v1.
set -euo pipefail

BASE_URL="${TWERVA_API_BASE_URL:-http://127.0.0.1:8000}"
EXAMPLE_EXTERNAL_KEY="example"
RUN_ID="$(date +%s)"

json_field() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)['"$1"'])'
}

json_id() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'
}

schedule_and_publish() {
  local artifact_id="$1"
  local account_id="$2"
  local scheduled_for="$3"
  local schedule_payload
  local schedule_response
  local post_job_id
  local post_job_status
  local publish_body
  local publish_status

  schedule_payload="{\"artifact_id\":\"${artifact_id}\",\"account_id\":\"${account_id}\",\"scheduled_for\":\"${scheduled_for}\"}"
  schedule_response="$(curl -sS -X POST "${BASE_URL}/api/v1/schedule" \
    -H 'Content-Type: application/json' \
    -d "${schedule_payload}")"
  echo "${schedule_response}" >&2
  post_job_id="$(printf '%s' "${schedule_response}" | json_id)"
  post_job_status="$(printf '%s' "${schedule_response}" | json_field '"status"')"

  if [[ "${post_job_status}" != "scheduled" ]]; then
    echo "expected post_job scheduled, got ${post_job_status}" >&2
    exit 1
  fi

  publish_body="$(curl -sS -X POST "${BASE_URL}/api/v1/publish/run/${post_job_id}")"
  echo "${publish_body}" >&2
  publish_status="$(printf '%s' "${publish_body}" | json_field '"status"')"

  if [[ "${publish_status}" != "published" ]]; then
    echo "expected published, got ${publish_status}" >&2
    exit 1
  fi

  printf '%s' "${post_job_id}"
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

echo "POST empty cluster (median null) + measure cluster + account"
EMPTY_CLUSTER_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/clusters" \
  -H 'Content-Type: application/json' \
  -d "{
    \"brand_id\": \"${BRAND_ID}\",
    \"slug\": \"measure-empty-${RUN_ID}\",
    \"name\": \"Empty measure lane\"
  }")"
echo "${EMPTY_CLUSTER_BODY}"
EMPTY_CLUSTER_ID="$(printf '%s' "${EMPTY_CLUSTER_BODY}" | json_id)"

EMPTY_SUMMARY="$(curl -sS "${BASE_URL}/api/v1/clusters/${EMPTY_CLUSTER_ID}/metrics/summary")"
echo "${EMPTY_SUMMARY}"
EMPTY_MEDIAN="$(printf '%s' "${EMPTY_SUMMARY}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["median_views"])')"

if [[ "${EMPTY_MEDIAN}" != "None" && "${EMPTY_MEDIAN}" != "null" ]]; then
  echo "expected empty median null, got ${EMPTY_MEDIAN}" >&2
  exit 1
fi

CLUSTER_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/clusters" \
  -H 'Content-Type: application/json' \
  -d "{
    \"brand_id\": \"${BRAND_ID}\",
    \"slug\": \"measure-lane-${RUN_ID}\",
    \"name\": \"Measure smoke lane\"
  }")"
echo "${CLUSTER_BODY}"
CLUSTER_ID="$(printf '%s' "${CLUSTER_BODY}" | json_id)"

ACCOUNT_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/accounts" \
  -H 'Content-Type: application/json' \
  -d "{
    \"cluster_id\": \"${CLUSTER_ID}\",
    \"platform\": \"instagram\",
    \"handle\": \"measure_smoke_${RUN_ID}\"
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

echo "Schedule + mock-publish three jobs"
JOB_ONE_ID="$(schedule_and_publish "${ARTIFACT_ID}" "${ACCOUNT_ID}" "2026-09-17T15:00:00Z")"
JOB_TWO_ID="$(schedule_and_publish "${ARTIFACT_ID}" "${ACCOUNT_ID}" "2026-09-17T16:00:00Z")"
JOB_THREE_ID="$(schedule_and_publish "${ARTIFACT_ID}" "${ACCOUNT_ID}" "2026-09-17T17:00:00Z")"
echo "post_jobs ${JOB_ONE_ID} ${JOB_TWO_ID} ${JOB_THREE_ID}"

echo "POST metrics 10 / 20 / 30"
METRICS_ONE="$(curl -sS -X POST "${BASE_URL}/api/v1/post-jobs/${JOB_ONE_ID}/metrics" \
  -H 'Content-Type: application/json' \
  -d '{"views":10,"likes":1,"comments":0,"shares":0}')"
echo "${METRICS_ONE}"
METRICS_TWO="$(curl -sS -X POST "${BASE_URL}/api/v1/post-jobs/${JOB_TWO_ID}/metrics" \
  -H 'Content-Type: application/json' \
  -d '{"views":20,"likes":2,"comments":1,"shares":0}')"
echo "${METRICS_TWO}"
METRICS_THREE="$(curl -sS -X POST "${BASE_URL}/api/v1/post-jobs/${JOB_THREE_ID}/metrics" \
  -H 'Content-Type: application/json' \
  -d '{"views":30,"likes":3,"comments":1,"shares":1}')"
echo "${METRICS_THREE}"

JOB_ONE_AFTER="$(curl -sS "${BASE_URL}/api/v1/post-jobs/${JOB_ONE_ID}")"
JOB_ONE_STATUS="$(printf '%s' "${JOB_ONE_AFTER}" | json_field '"status"')"

if [[ "${JOB_ONE_STATUS}" != "measured" ]]; then
  echo "expected measured after metrics, got ${JOB_ONE_STATUS}" >&2
  exit 1
fi

echo "GET cluster metrics summary (median 20)"
SUMMARY_BODY="$(curl -sS "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}/metrics/summary")"
echo "${SUMMARY_BODY}"
MEDIAN_VIEWS="$(printf '%s' "${SUMMARY_BODY}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["median_views"])')"
VIEWS_JOB_COUNT="$(printf '%s' "${SUMMARY_BODY}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["views_job_count"])')"

if [[ "${MEDIAN_VIEWS}" != "20.0" && "${MEDIAN_VIEWS}" != "20" ]]; then
  echo "expected median 20, got ${MEDIAN_VIEWS}" >&2
  exit 1
fi

if [[ "${VIEWS_JOB_COUNT}" != "3" ]]; then
  echo "expected views_job_count 3, got ${VIEWS_JOB_COUNT}" >&2
  exit 1
fi

echo "POST stub metrics on job one (mock-published)"
STUB_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/post-jobs/${JOB_ONE_ID}/metrics/stub")"
echo "${STUB_BODY}"
STUB_VIEWS="$(printf '%s' "${STUB_BODY}" | json_field '"views"')"

if [[ "${STUB_VIEWS}" != "100" ]]; then
  echo "expected stub views 100, got ${STUB_VIEWS}" >&2
  exit 1
fi

AFTER_STUB_SUMMARY="$(curl -sS "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}/metrics/summary")"
echo "${AFTER_STUB_SUMMARY}"
AFTER_STUB_MEDIAN="$(printf '%s' "${AFTER_STUB_SUMMARY}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["median_views"])')"

# latest-wins: 100, 20, 30 → median 30
if [[ "${AFTER_STUB_MEDIAN}" != "30.0" && "${AFTER_STUB_MEDIAN}" != "30" ]]; then
  echo "expected median 30 after stub latest-wins, got ${AFTER_STUB_MEDIAN}" >&2
  exit 1
fi

echo "POST steer pause"
PAUSE_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}/steer" \
  -H 'Content-Type: application/json' \
  -d '{"action":"pause","reason":"smoke pause"}')"
echo "${PAUSE_BODY}"
PAUSED_CLUSTER="$(curl -sS "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}")"
PAUSED_ACTIVE="$(printf '%s' "${PAUSED_CLUSTER}" | json_field '"is_active"')"

if [[ "${PAUSED_ACTIVE}" != "False" && "${PAUSED_ACTIVE}" != "false" ]]; then
  echo "expected is_active false after pause, got ${PAUSED_ACTIVE}" >&2
  exit 1
fi

echo "POST steer double_down (log-only)"
DOUBLE_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}/steer" \
  -H 'Content-Type: application/json' \
  -d '{"action":"double_down","reason":"smoke log only"}')"
echo "${DOUBLE_BODY}"
STILL_PAUSED="$(curl -sS "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}")"
STILL_ACTIVE="$(printf '%s' "${STILL_PAUSED}" | json_field '"is_active"')"

if [[ "${STILL_ACTIVE}" != "False" && "${STILL_ACTIVE}" != "false" ]]; then
  echo "expected is_active still false after double_down, got ${STILL_ACTIVE}" >&2
  exit 1
fi

echo "POST steer resume"
RESUME_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}/steer" \
  -H 'Content-Type: application/json' \
  -d '{"action":"resume"}')"
echo "${RESUME_BODY}"
RESUMED_CLUSTER="$(curl -sS "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}")"
RESUMED_ACTIVE="$(printf '%s' "${RESUMED_CLUSTER}" | json_field '"is_active"')"

if [[ "${RESUMED_ACTIVE}" != "True" && "${RESUMED_ACTIVE}" != "true" ]]; then
  echo "expected is_active true after resume, got ${RESUMED_ACTIVE}" >&2
  exit 1
fi

echo "GET agent-summary JSON + markdown"
AGENT_JSON="$(curl -sS "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}/agent-summary")"
echo "${AGENT_JSON}"
AGENT_STEER_COUNT="$(printf '%s' "${AGENT_JSON}" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["recent_steer_actions"]))')"
AGENT_MEDIAN="$(printf '%s' "${AGENT_JSON}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["metrics"]["median_views"])')"

if [[ "${AGENT_STEER_COUNT}" != "3" ]]; then
  echo "expected 3 steer actions in summary, got ${AGENT_STEER_COUNT}" >&2
  exit 1
fi

if [[ "${AGENT_MEDIAN}" != "30.0" && "${AGENT_MEDIAN}" != "30" ]]; then
  echo "expected agent-summary median 30, got ${AGENT_MEDIAN}" >&2
  exit 1
fi

AGENT_MD="$(curl -sS "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}/agent-summary?format=markdown")"
echo "${AGENT_MD}"

if ! printf '%s' "${AGENT_MD}" | grep -q "median views: 30"; then
  echo "markdown summary missing median views: 30" >&2
  exit 1
fi

if ! printf '%s' "${AGENT_MD}" | grep -q "pause"; then
  echo "markdown summary missing pause steer" >&2
  exit 1
fi

echo "1.7d-ii smoke OK  cluster=${CLUSTER_ID} median_after_stub=${AFTER_STUB_MEDIAN} jobs=${JOB_ONE_ID},${JOB_TWO_ID},${JOB_THREE_ID}"
