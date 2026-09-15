#!/usr/bin/env bash
# 1.9a-iii dry-run: sources on cluster X (or ingest when Spotmu is up) →
# generate carousel drafts → STOP before approve (human gate).
# Optional GET cluster agent-summary. Never approve / schedule / publish / steer.
#
# Usage (API already running, DATABASE_URL applied, schema migrated):
#   tools/agent_batch_generate.sh
#   TWERVA_API_BASE_URL=http://127.0.0.1:8000 tools/agent_batch_generate.sh
#   CLUSTER_SLUG=spotmu-general SPOTMU_INGEST=1 tools/agent_batch_generate.sh
#   CLUSTER_ID=<uuid> FETCH_SUMMARY=0 MAX_SOURCES=3 tools/agent_batch_generate.sh
#
# Public nginx on twerva.com stays /health only — use loopback or an SSH
# tunnel for /api/v1.
set -euo pipefail

BASE_URL="${TWERVA_API_BASE_URL:-http://127.0.0.1:8000}"
CLUSTER_SLUG="${CLUSTER_SLUG:-spotmu-general}"
CLUSTER_ID="${CLUSTER_ID:-}"
SPOTMU_SMOKE_SLUG="${SPOTMU_SMOKE_SLUG:-ai-agents}"
SPOTMU_INGEST="${SPOTMU_INGEST:-auto}"
FETCH_SUMMARY="${FETCH_SUMMARY:-1}"
MAX_SOURCES="${MAX_SOURCES:-20}"
EXAMPLE_EXTERNAL_KEY="example"

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

if [[ -z "${CLUSTER_ID}" ]]; then
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
    CLUSTER_ID="$(printf '%s' "${LIST_CLUSTERS}" | CLUSTER_SLUG="${CLUSTER_SLUG}" python3 -c '
import json, sys, os
cluster_slug = os.environ["CLUSTER_SLUG"]
clusters = json.load(sys.stdin)
for cluster in clusters:
    if cluster.get("slug") == cluster_slug:
        print(cluster["id"])
        break
else:
    raise SystemExit(f"{cluster_slug} cluster not found after POST conflict")
')"
  fi
else
  echo "Using CLUSTER_ID=${CLUSTER_ID}"
fi

echo "GET /api/v1/clusters/${CLUSTER_ID}"
CLUSTER_GET="$(curl -sS "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}")"
echo "${CLUSTER_GET}"

SOURCE_ITEM_IDS="$(printf '%s' "${CLUSTER_GET}" | python3 -c '
import json, sys
cluster = json.load(sys.stdin)
ids = cluster.get("source_item_ids") or []
print(" ".join(ids))
')"

should_ingest="no"

if [[ "${SPOTMU_INGEST}" == "1" ]]; then
  should_ingest="yes"
elif [[ "${SPOTMU_INGEST}" == "auto" && -z "${SOURCE_ITEM_IDS}" ]]; then
  should_ingest="yes"
fi

INGEST_NOTE="used existing cluster sources"

if [[ "${should_ingest}" == "yes" ]]; then
  echo "POST /api/v1/ingest/spotmu/interests/${SPOTMU_SMOKE_SLUG}"
  INGEST_TMP="$(mktemp)"
  INGEST_CODE="$(curl -sS -o "${INGEST_TMP}" -w "%{http_code}" -X POST \
    "${BASE_URL}/api/v1/ingest/spotmu/interests/${SPOTMU_SMOKE_SLUG}" || true)"
  INGEST_BODY="$(cat "${INGEST_TMP}")"
  rm -f "${INGEST_TMP}"
  echo "ingest HTTP ${INGEST_CODE}"
  echo "${INGEST_BODY}"

  if [[ "${INGEST_CODE}" == "200" ]] && printf '%s' "${INGEST_BODY}" | python3 -c 'import json,sys; json.load(sys.stdin)["id"]' >/dev/null 2>&1; then
    INGESTED_ID="$(printf '%s' "${INGEST_BODY}" | json_id)"
    echo "POST /api/v1/clusters/${CLUSTER_ID}/source-items/${INGESTED_ID}"
    ATTACH_BODY="$(curl -sS -X POST \
      "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}/source-items/${INGESTED_ID}")"
    echo "${ATTACH_BODY}"
    INGEST_NOTE="ingested slug=${SPOTMU_SMOKE_SLUG} source_item=${INGESTED_ID}"
  else
    echo "Spotmu ingest skipped or failed (HTTP ${INGEST_CODE}); falling back to existing/seed sources" >&2
    INGEST_NOTE="ingest failed HTTP ${INGEST_CODE}; fallback"
  fi
fi

CLUSTER_GET="$(curl -sS "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}")"
SOURCE_ITEM_IDS="$(printf '%s' "${CLUSTER_GET}" | python3 -c '
import json, sys
cluster = json.load(sys.stdin)
ids = cluster.get("source_item_ids") or []
print(" ".join(ids))
')"

if [[ -z "${SOURCE_ITEM_IDS}" ]]; then
  echo "Cluster has no source_item_ids; attaching seed example if present"
  LIST_SOURCES="$(curl -sS "${BASE_URL}/api/v1/source-items")"
  EXAMPLE_ID="$(printf '%s' "${LIST_SOURCES}" | python3 -c '
import json, sys
source_items = json.load(sys.stdin)
for source_item in source_items:
    if source_item.get("external_key") == "example":
        print(source_item["id"])
        break
')"

  if [[ -z "${EXAMPLE_ID}" ]]; then
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
          \"Seed-shaped dry-run row — not a live Spotmu fetch.\"
        ],
        \"canonical_url\": \"https://spotmu.com/interest/example\"
      }")"
    echo "${SOURCE_BODY}"
    EXAMPLE_ID="$(printf '%s' "${SOURCE_BODY}" | json_id)"
  fi

  echo "POST /api/v1/clusters/${CLUSTER_ID}/source-items/${EXAMPLE_ID}"
  ATTACH_EXAMPLE="$(curl -sS -X POST \
    "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}/source-items/${EXAMPLE_ID}")"
  echo "${ATTACH_EXAMPLE}"
  SOURCE_ITEM_IDS="${EXAMPLE_ID}"
  INGEST_NOTE="${INGEST_NOTE}; attached seed example ${EXAMPLE_ID}"
fi

CAPPED_SOURCE_IDS="$(printf '%s' "${SOURCE_ITEM_IDS}" | MAX_SOURCES="${MAX_SOURCES}" python3 -c '
import os, sys
max_sources = int(os.environ.get("MAX_SOURCES", "20"))
ids = sys.stdin.read().split()
print(" ".join(ids[:max_sources]))
')"

if [[ -z "${CAPPED_SOURCE_IDS}" ]]; then
  echo "no source_item_ids to generate from" >&2
  exit 1
fi

echo "Generating carousels for: ${CAPPED_SOURCE_IDS}"
ARTIFACT_IDS=""
ARTIFACT_COUNT=0

for SOURCE_ITEM_ID in ${CAPPED_SOURCE_IDS}; do
  echo "POST /api/v1/generate/carousel source_item_id=${SOURCE_ITEM_ID} cluster_id=${CLUSTER_ID}"
  GENERATE_TMP="$(mktemp)"
  GENERATE_CODE="$(curl -sS -o "${GENERATE_TMP}" -w "%{http_code}" -X POST \
    "${BASE_URL}/api/v1/generate/carousel" \
    -H 'Content-Type: application/json' \
    -d "{\"source_item_id\": \"${SOURCE_ITEM_ID}\", \"cluster_id\": \"${CLUSTER_ID}\"}")"
  GENERATE_BODY="$(cat "${GENERATE_TMP}")"
  rm -f "${GENERATE_TMP}"
  echo "generate HTTP ${GENERATE_CODE}"
  echo "${GENERATE_BODY}"

  if [[ "${GENERATE_CODE}" != "201" ]]; then
    echo "expected generate HTTP 201, got ${GENERATE_CODE}" >&2
    exit 1
  fi

  ARTIFACT_ID="$(printf '%s' "${GENERATE_BODY}" | json_id)"
  ARTIFACT_STATUS="$(printf '%s' "${GENERATE_BODY}" | json_field '"status"')"

  if [[ "${ARTIFACT_STATUS}" != "draft" ]]; then
    echo "expected artifact status draft, got ${ARTIFACT_STATUS}" >&2
    exit 1
  fi

  ARTIFACT_IDS="${ARTIFACT_IDS} ${ARTIFACT_ID}"
  ARTIFACT_COUNT=$((ARTIFACT_COUNT + 1))
done

echo "GET /api/v1/artifacts?status=draft (queue; not approving)"
DRAFT_QUEUE="$(curl -sS "${BASE_URL}/api/v1/artifacts?status=draft")"
DRAFT_COUNT="$(printf '%s' "${DRAFT_QUEUE}" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')"
echo "draft queue length=${DRAFT_COUNT}"

if [[ "${FETCH_SUMMARY}" != "0" ]]; then
  echo "GET /api/v1/clusters/${CLUSTER_ID}/agent-summary (optional)"
  SUMMARY_BODY="$(curl -sS "${BASE_URL}/api/v1/clusters/${CLUSTER_ID}/agent-summary")"
  echo "${SUMMARY_BODY}"
fi

echo
echo "HUMAN GATE — stop before approve. Do not POST /artifacts/{id}/approve from this script."
echo "Review drafts on ops Queue (http://127.0.0.1:5173) or GET /api/v1/artifacts?status=draft"
echo "1.9a-iii dry-run OK  cluster=${CLUSTER_ID} brand=${BRAND_ID} generated=${ARTIFACT_COUNT} artifacts=${ARTIFACT_IDS} note=${INGEST_NOTE}"
