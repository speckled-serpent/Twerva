#!/usr/bin/env bash
# 1.4e-iii smoke: generate a carousel from a DB source (seeded or created)
# and GET the Artifact. Does not call Spotmu — works offline.
#
# Usage (API already running, DATABASE_URL applied, schema migrated):
#   tools/smoke_1_4_carousel.sh
#   TWERVA_API_BASE_URL=http://127.0.0.1:8000 tools/smoke_1_4_carousel.sh
#
# Public nginx on twerva.com stays /health only — use loopback or an SSH
# tunnel for /api/v1.
set -euo pipefail

BASE_URL="${TWERVA_API_BASE_URL:-http://127.0.0.1:8000}"
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

echo "POST /api/v1/generate/carousel"
GENERATE_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/generate/carousel" \
  -H 'Content-Type: application/json' \
  -d "{\"source_item_id\": \"${SOURCE_ITEM_ID}\"}")"
echo "${GENERATE_BODY}"
ARTIFACT_ID="$(printf '%s' "${GENERATE_BODY}" | json_id)"
ARTIFACT_STATUS="$(printf '%s' "${GENERATE_BODY}" | json_field '"status"')"
ARTIFACT_FORMAT="$(printf '%s' "${GENERATE_BODY}" | json_field '"format"')"
ARTIFACT_CAPTION="$(printf '%s' "${GENERATE_BODY}" | json_field '"caption"')"

if [[ "${ARTIFACT_STATUS}" != "draft" ]]; then
  echo "expected artifact status draft, got ${ARTIFACT_STATUS}" >&2
  exit 1
fi

if [[ "${ARTIFACT_FORMAT}" != "carousel" ]]; then
  echo "expected format carousel, got ${ARTIFACT_FORMAT}" >&2
  exit 1
fi

if [[ -z "${ARTIFACT_CAPTION}" || "${ARTIFACT_CAPTION}" == "None" ]]; then
  echo "expected non-empty caption" >&2
  exit 1
fi

SLIDE_COUNT="$(printf '%s' "${GENERATE_BODY}" | python3 -c '
import json, sys
artifact = json.load(sys.stdin)
slides = artifact.get("slides") or []
if len(slides) < 3:
    raise SystemExit(f"expected at least 3 slides, got {len(slides)}")
for slide in slides:
    if not slide.get("role") or not slide.get("text") or not slide.get("asset_ref"):
        raise SystemExit(f"slide missing role/text/asset_ref: {slide}")
print(len(slides))
')"

echo "GET /api/v1/artifacts/${ARTIFACT_ID}"
GET_BODY="$(curl -sS "${BASE_URL}/api/v1/artifacts/${ARTIFACT_ID}")"
echo "${GET_BODY}"
GET_ID="$(printf '%s' "${GET_BODY}" | json_id)"

if [[ "${GET_ID}" != "${ARTIFACT_ID}" ]]; then
  echo "GET artifact id mismatch" >&2
  exit 1
fi

echo "POST /api/v1/generate/carousel (second run keeps history)"
SECOND_BODY="$(curl -sS -X POST "${BASE_URL}/api/v1/generate/carousel" \
  -H 'Content-Type: application/json' \
  -d "{\"source_item_id\": \"${SOURCE_ITEM_ID}\"}")"
SECOND_ID="$(printf '%s' "${SECOND_BODY}" | json_id)"

if [[ "${SECOND_ID}" == "${ARTIFACT_ID}" ]]; then
  echo "expected a new artifact id on re-generate, got ${SECOND_ID}" >&2
  exit 1
fi

echo "1.4e-iii smoke OK  source_item=${SOURCE_ITEM_ID} artifact=${ARTIFACT_ID} slides=${SLIDE_COUNT} second_artifact=${SECOND_ID} brand=${BRAND_ID}"
