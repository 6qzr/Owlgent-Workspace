#!/usr/bin/env bash
# Smoke test for a running deployment (issue #19):
# health → start → message → book → approve → fetch history.
#
# Usage: scripts/smoke.sh [BASE_URL]        (default http://localhost:8000)
# Every run books a Dentistry slot for tomorrow, then cancels it: a cancellation always pauses
# for staff, so step_approve has an approval to decide at any time of day, and the approved
# cancellation frees the slot again. The seed only covers 5 days from when the database
# volume was created, so on a stack left running longer than that "tomorrow" has no slots
# and step_book fails; recreate the stack (docker compose down -v) to reseed.
# SMOKE_EMERGENCY=1 also sends an emergency in its own conversation (FR-6). It is off by
# default because every run stores a real staff flag that staff can't clear, so it is for
# throwaway stacks such as CI, never for a deployment staff use.
# Needs: bash, curl, jq. Exits non-zero with a FAIL line on the first failed step.
#
# Adding steps: write a step_<name> function that calls `request` and checks the body with
# `expect`, then add it to STEPS below.

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
BASE_URL="${BASE_URL%/}"
MESSAGE="What are your opening hours?"
# Caught by the rule-based safety gate, so it works with any LLM provider.
EMERGENCY_MESSAGE="I have chest pain"
# Booking takes two turns: list tomorrow's slots, then book one by its number in that list.
# "tomorrow" matters: a same-day slot would pause at the booking, not at the cancellation.
# Worded for the fake provider too: the name follows "my name is", the phone has 8+ digits.
BOOK_SLOTS_MESSAGE="Show me free dentistry slots tomorrow"
BOOK_MESSAGE="book number 1, my name is Ali Salem, phone 91234567"
# The booking number from this reply is the one cancelled.
BOOKING_NUMBER_PATTERN='Your booking number is ([0-9]+)'
APPROVAL_DECISION='{"approved": true, "reason": "Slot is free", "staff": "smoke-test"}'
CURL_TIMEOUT_SECONDS=30 # covers one LLM turn; the app's own LLM timeout is shorter

BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT

# Values passed from one step to the next.
CONVERSATION_ID=""
STARTED_ID=""
APPROVAL_ID=""
RESPONSE=""

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

# send_message CONVERSATION_ID TEXT — sends one patient message; the reply is in RESPONSE.
send_message() {
  local body
  body="$(jq -n --arg message "$2" '{message: $message}')"
  request POST "/api/v1/conversations/$1/messages" 200 "$body"
}

step_health() {
  request GET /health 200
  expect '.status == "ok" and .database == "ok"' "health: service or database is not ok"
  pass "GET /health: service and database ok"
}

step_start_conversation() {
  start_conversation
  CONVERSATION_ID="$STARTED_ID"
  pass "POST /api/v1/conversations: started $CONVERSATION_ID"
}

step_send_message() {
  send_message "$CONVERSATION_ID" "$MESSAGE"
  expect '.reply | type == "string" and length > 0' "message: the reply is empty"
  expect '.status | IN("answered", "clarifying", "awaiting_approval", "emergency")' \
    "message: unknown status"
  pass "POST .../messages: got a reply (status $(json_field '.status'))"
}

# Book tomorrow's slot (confirmed at once), then cancel it: a cancellation always waits for
# staff, so the graph pauses whatever the time of day; sets APPROVAL_ID.
step_book() {
  send_message "$CONVERSATION_ID" "$BOOK_SLOTS_MESSAGE"
  expect '.reply | type == "string" and length > 0' "book: no list of free slots"
  send_message "$CONVERSATION_ID" "$BOOK_MESSAGE"
  expect '.status == "answered"' "book: expected a future booking to be confirmed (status answered)"
  local reply booking_id
  reply="$(json_field '.reply')"
  if [[ ! "$reply" =~ $BOOKING_NUMBER_PATTERN ]]; then
    fail "book: no booking number in the confirmation (has its wording changed?). Body: $RESPONSE"
  fi
  booking_id="${BASH_REMATCH[1]}"
  # The fake provider reads the first number in the message as the booking id, so the
  # message carries no other digits.
  send_message "$CONVERSATION_ID" "cancel booking $booking_id"
  expect '.status == "awaiting_approval"' "cancel: expected status awaiting_approval"
  expect '.approval_id | type == "number" and . == floor' "cancel: approval_id is not an integer"
  APPROVAL_ID="$(json_field '.approval_id')"
  pass "book: booked $booking_id for tomorrow, cancel waits for staff (approval $APPROVAL_ID)"
}

step_approve() {
  request POST "/api/v1/approvals/$APPROVAL_ID/decision" 200 "$APPROVAL_DECISION"
  expect '.outcome | type == "string" and length > 0' "approve: no outcome for the patient"
  pass "POST /api/v1/approvals/$APPROVAL_ID/decision: $(json_field '.outcome')"
}

step_fetch_history() {
  request GET "/api/v1/conversations/$CONVERSATION_ID" 200
  expect '.messages | length >= 2' "history: expected at least the message and its reply"
  expect '.messages[0].role == "patient" and .messages[0].content == $message' \
    "history: the first message is not the one sent" --arg message "$MESSAGE"
  expect 'any(.messages[]; .role == "assistant" and (.content | length > 0))' \
    "history: no assistant reply stored"
  pass "GET .../$CONVERSATION_ID: history has $(json_field '.messages | length') messages"
}

# A new conversation, so the emergency never mixes with the history checked above.
step_emergency() {
  start_conversation
  send_message "$STARTED_ID" "$EMERGENCY_MESSAGE"
  expect '.status == "emergency" and (.reply | length > 0)' \
    "emergency: expected status emergency with the instruction"
  # The endpoint's largest page, so the new flag is found even on a busy stack.
  request GET "/api/v1/emergencies?limit=200" 200
  expect 'any(.[]; .conversation_id == $id)' \
    "emergency: no staff flag stored for the conversation" --arg id "$STARTED_ID"
  pass "emergency: short-circuited and flagged for staff"
}

STEPS=(
  step_health
  step_start_conversation
  step_send_message
  step_book
  step_approve
  step_fetch_history
)
if [[ "${SMOKE_EMERGENCY:-0}" == "1" ]]; then
  STEPS+=(step_emergency)
fi

command -v curl >/dev/null || fail "curl is not installed"
command -v jq >/dev/null || fail "jq is not installed (Git Bash: winget install jqlang.jq)"

echo "Smoke test against $BASE_URL"
for step in "${STEPS[@]}"; do
  "$step"
done
echo "All ${#STEPS[@]} smoke steps passed."
