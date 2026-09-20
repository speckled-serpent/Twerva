# Shared ops login for loopback smoke / agent scripts.
# Source after BASE_URL is set. Health stays unauthenticated; later curls
# pick up the session cookie via the `curl` function override.
#
# Requires OPS_ADMIN_USERNAME and OPS_ADMIN_PASSWORD in the environment
# (same values used to bootstrap the first ops_users row).
#
# Usage from a script in tools/:
#   # shellcheck source=lib/ops_session.sh
#   source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/ops_session.sh"
#   ops_begin_authenticated_curl "${BASE_URL}"

ops_begin_authenticated_curl() {
  local base_url="${1:-}"
  local username="${OPS_ADMIN_USERNAME:-}"
  local password="${OPS_ADMIN_PASSWORD:-}"
  local login_body
  local login_json
  local login_status

  if [[ -z "${base_url}" ]]; then
    echo "ops_begin_authenticated_curl: BASE_URL is required" >&2
    return 1
  fi

  if [[ -z "${username}" || -z "${password}" ]]; then
    echo "Set OPS_ADMIN_USERNAME and OPS_ADMIN_PASSWORD so smokes can POST /api/v1/auth/login." >&2
    return 1
  fi

  OPS_COOKIE_JAR="$(mktemp)"
  login_json="$(python3 -c 'import json, os; print(json.dumps({"username": os.environ["OPS_ADMIN_USERNAME"], "password": os.environ["OPS_ADMIN_PASSWORD"]}))')"
  login_body="$(command curl -sS -c "${OPS_COOKIE_JAR}" -b "${OPS_COOKIE_JAR}" \
    -o /tmp/twerva_ops_login_body \
    -w "%{http_code}" \
    -X POST "${base_url}/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "${login_json}")"
  login_status="${login_body}"

  if [[ "${login_status}" != "200" ]]; then
    echo "ops login failed (HTTP ${login_status}):" >&2
    cat /tmp/twerva_ops_login_body >&2 || true
    echo >&2
    return 1
  fi

  curl() {
    command curl -b "${OPS_COOKIE_JAR}" -c "${OPS_COOKIE_JAR}" "$@"
  }
}
