# Shared HTTP helpers for scripts/smoke.sh and scripts/demo.sh. Source it; don't run it.
# Callers set BASE_URL, CURL_TIMEOUT_SECONDS and BODY_FILE (a temp file) first.
# Needs: bash, curl, jq.

RESPONSE=""
STARTED_ID=""

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

pass() {
  echo "PASS: $*"
}

# request METHOD PATH EXPECTED_STATUS [JSON_BODY] — sets RESPONSE, or fails with the details.
request() {
  local method="$1" path="$2" expected="$3" body="${4:-}"
  local args=(--silent --show-error --max-time "$CURL_TIMEOUT_SECONDS"
    --output "$BODY_FILE" --write-out '%{http_code}' --request "$method")
  if [[ -n "$body" ]]; then
    args+=(--header 'Content-Type: application/json' --data "$body")
  fi
  local code
  if ! code="$(curl "${args[@]}" "$BASE_URL$path")"; then
    fail "$method $path: could not reach $BASE_URL (is the API running?)"
  fi
  RESPONSE="$(tr -d '\r' <"$BODY_FILE")"
  if [[ "$code" != "$expected" ]]; then
    fail "$method $path: expected HTTP $expected, got $code. Body: $RESPONSE"
  fi
}

# expect JQ_FILTER DESCRIPTION [JQ_ARGS...] — fails unless the filter is true for RESPONSE.
expect() {
  local filter="$1" description="$2"
  shift 2
  if ! jq -e "$@" "$filter" >/dev/null 2>&1 <<<"$RESPONSE"; then
    fail "$description. Body: $RESPONSE"
  fi
}

# json_field JQ_FILTER — prints one value from RESPONSE (no trailing CR from Windows jq).
json_field() {
  jq -r "$1" <<<"$RESPONSE" | tr -d '\r'
}

# start_conversation — starts a conversation and checks its id; sets STARTED_ID.
start_conversation() {
  request POST /api/v1/conversations 201
  expect '.conversation_id | type == "string" and length > 0' "start: no conversation_id"
  STARTED_ID="$(json_field '.conversation_id')"
}

# send_message CONVERSATION_ID TEXT [EXPECTED_STATUS] — sends one patient message.
send_message() {
  local body
  body="$(jq -n --arg message "$2" '{message: $message}')"
  request POST "/api/v1/conversations/$1/messages" "${3:-200}" "$body"
}

require_tools() {
  command -v curl >/dev/null || fail "curl is not installed"
  command -v jq >/dev/null || fail "jq is not installed (Git Bash: winget install jqlang.jq)"
}
