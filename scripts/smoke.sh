#!/usr/bin/env bash
# Smoke test for a running deployment (issue #19): health → start → message → fetch history.
#
# Usage: scripts/smoke.sh [BASE_URL]        (default http://localhost:8000)
# SMOKE_EMERGENCY=1 also sends an emergency in its own conversation (FR-6). It is off by
# default because every run stores a real staff flag that staff can't clear, so it is for
# throwaway stacks such as CI, never for a deployment staff use.
# Needs: bash, curl, jq. Exits non-zero with a FAIL line on the first failed step.
#
# It stays read-mostly on purpose: booking and approval would leave real bookings on a
# deployment staff use. scripts/demo.sh runs every scenario, for throwaway or demo stacks.
#
# Adding steps: write a step_<name> function that calls `request` and checks the body with
# `expect` (helpers in scripts/lib/api.sh), then add it to STEPS below.

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
BASE_URL="${BASE_URL%/}"
MESSAGE="What are your opening hours?"
# Caught by the rule-based safety gate, so it works with any LLM provider.
EMERGENCY_MESSAGE="I have chest pain"
CURL_TIMEOUT_SECONDS=30 # covers one LLM turn; the app's own LLM timeout is shorter

BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT

# shellcheck source=lib/api.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib/api.sh"

# Passed from one step to the next.
CONVERSATION_ID=""

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
  step_fetch_history
)
if [[ "${SMOKE_EMERGENCY:-0}" == "1" ]]; then
  STEPS+=(step_emergency)
fi

require_tools

echo "Smoke test against $BASE_URL"
for step in "${STEPS[@]}"; do
  "$step"
done
echo "All ${#STEPS[@]} smoke steps passed."
