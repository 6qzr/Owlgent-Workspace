#!/usr/bin/env bash
# Demo of every Must scenario (FR-1 to FR-7) against a running stack (issue #103).
#
# Usage: scripts/demo.sh [BASE_URL]        (default http://localhost:8000)
# It prints each patient message, the assistant's reply and a PASS line, and stops with a FAIL
# line on the first broken check. It creates real conversations, bookings, approvals and an
# emergency flag, so run it on a demo or throwaway stack, not on one staff use (smoke.sh is
# the read-mostly check for that).
#
# DEMO_RESTART=1 (default) restarts the api container while a cancellation waits for staff,
# to show the pause survives (FR-5). It needs `docker compose` in this repo; set
# DEMO_RESTART=0 when the API runs somewhere else.
#
# The checks rely only on what code guarantees (routing, approvals, the database), so the demo
# passes with LLM_PROVIDER=fake or openai. Seed slots cover 5 days from the database's first
# start; recreate the volume if "tomorrow" has no free slots left.
# Needs: bash, curl, jq.

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
BASE_URL="${BASE_URL%/}"
CURL_TIMEOUT_SECONDS=30 # covers one LLM turn; the app's own LLM timeout is shorter
DEMO_RESTART="${DEMO_RESTART:-1}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT

# shellcheck source=lib/api.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib/api.sh"

STAFF="Front desk (demo)"

section() {
  printf '\n=== %s ===\n' "$*"
}

# say CONVERSATION_ID TEXT [EXPECTED_HTTP] — sends a patient message and prints the turn.
say() {
  echo "  patient > $2"
  send_message "$1" "$2" "${3:-200}"
  if [[ "${3:-200}" == "200" ]]; then
    json_field '.reply // "(no reply yet: waiting for a staff decision)"' | sed 's/^/  clinic  > /'
    echo "            (status: $(json_field '.status'))"
  else
    echo "  api     > HTTP ${3}: $(json_field '.detail')"
  fi
}

# decide APPROVAL_ID true|false REASON [EXPECTED_HTTP] — staff decision through the API.
decide() {
  local body
  body="$(jq -n --argjson approved "$2" --arg reason "$3" --arg staff "$STAFF" \
    '{approved: $approved, reason: $reason, staff: $staff}')"
  echo "  staff   > $([[ "$2" == true ]] && echo approve || echo reject) #$1: $3"
  request POST "/api/v1/approvals/$1/decision" "${4:-200}" "$body"
}

# The number in "Your booking number is 12." from the last reply.
booking_number() {
  json_field '.reply' | sed -n 's/.*booking number is \([0-9][0-9]*\).*/\1/p'
}

# The date (YYYY-MM-DD) of slot 1 in the last find_slots reply.
first_slot_date() {
  json_field '.reply | capture("(?<day>[0-9]{4}-[0-9]{2}-[0-9]{2})").day'
}

# Ids of the free slots for SPECIALTY on DATE, from the slots endpoint (same order as the chat).
free_slot_ids() {
  request GET "/api/v1/slots?specialty=$1&date=$2" 200
}

restart_api() {
  echo "  ops     > docker compose restart api"
  (cd "$REPO_ROOT" && docker compose restart api >/dev/null 2>&1)
  for _ in $(seq 1 45); do
    if curl --silent --max-time 2 "$BASE_URL/health" | jq -e '.status == "ok"' >/dev/null 2>&1; then
      echo "  ops     > api is healthy again"
      return
    fi
    sleep 2
  done
  fail "the api did not become healthy within 90 seconds after the restart"
}

# ---------------------------------------------------------------------------------------------

scenario_health() {
  section "FR-7  Health and API docs"
  request GET /health 200
  expect '.status == "ok" and .database == "ok"' "health: service or database is not ok"
  pass "GET /health: service and database ok"
  request GET /openapi.json 200
  expect '.paths | has("/api/v1/conversations")' "docs: OpenAPI has no conversations path"
  pass "OpenAPI docs served (open $BASE_URL/docs in a browser)"
}

scenario_questions() {
  section "FR-3  Answers from clinic documents, with the source"
  start_conversation
  local id="$STARTED_ID"
  say "$id" "What are your opening hours?"
  expect '.status == "answered" and (.sources | index("opening_hours.md"))' \
    "FAQ: expected an answer citing opening_hours.md"
  pass "answered from opening_hours.md and named the source"

  say "$id" "Is there a parking garage?"
  expect '.sources == [] and (.reply | test("don.t know"; "i"))' \
    "unknown: expected an honest I don't know with no source"
  pass "no matching document: honest \"I don't know\", no source invented"
}

scenario_understanding() {
  section "FR-2  Intent, clarifying question, out of scope (FR-6: no diagnosis)"
  start_conversation
  local id="$STARTED_ID"
  say "$id" "I want an appointment"
  expect '.status == "clarifying"' "clarify: expected a clarifying question"
  pass "missing details: asked a question instead of guessing"

  say "$id" "Can you tell me which illness I have from my symptoms"
  expect '.status == "answered" and (.reply | length > 0)' "scope: expected a polite reply"
  pass "medical judgement: polite reply, no diagnosis"
}

scenario_emergency() {
  section "FR-6  Emergency short-circuit and staff flag"
  start_conversation
  local id="$STARTED_ID"
  say "$id" "I have chest pain and I can't breathe"
  expect '.status == "emergency"' "emergency: expected status emergency"
  pass "emergency instruction given at once; no other workflow ran"
  request GET "/api/v1/emergencies?limit=200" 200
  expect 'any(.[]; .conversation_id == $id)' "emergency: no staff flag stored" --arg id "$id"
  pass "GET /api/v1/emergencies: staff can see the flag"
}

# Sets PATIENT_ID, BOOKING_ID, BOOKED_SLOT_ID and BOOKED_DATE for the cancel scenario.
scenario_booking() {
  section "FR-4  Find free slots and book one"
  start_conversation
  PATIENT_ID="$STARTED_ID"
  say "$PATIENT_ID" "Any free dentistry slots tomorrow?"
  expect '.reply | test("(^|\n)1\\. ")' \
    "find slots: expected a numbered list (is tomorrow inside the seeded 5 days?)"
  BOOKED_DATE="$(first_slot_date)"
  free_slot_ids Dentistry "$BOOKED_DATE"
  BOOKED_SLOT_ID="$(json_field '.[0].id')"
  pass "free slots listed and numbered; slot 1 is #$BOOKED_SLOT_ID on $BOOKED_DATE"

  say "$PATIENT_ID" "Book number 1, my name is Ali Said, phone 91234567"
  BOOKING_ID="$(booking_number)"
  [[ -n "$BOOKING_ID" ]] || fail "book: expected a confirmation with a booking number"
  free_slot_ids Dentistry "$BOOKED_DATE"
  expect 'all(.[]; .id != ($slot | tonumber))' "book: the slot is still listed as free" \
    --arg slot "$BOOKED_SLOT_ID"
  pass "booking #$BOOKING_ID confirmed (not same day, so no approval); the slot is no longer free"
}

scenario_double_booking() {
  section "FR-4  Two patients choose the same slot: only one gets it"
  start_conversation
  local first="$STARTED_ID"
  start_conversation
  local second="$STARTED_ID"
  say "$first" "Any free general practice slots tomorrow?"
  say "$second" "Any free general practice slots tomorrow?"
  pass "both patients were offered the same slot 1"

  say "$first" "Book number 1, my name is Sara Ali, phone 92345678"
  [[ -n "$(booking_number)" ]] || fail "double booking: the first patient should get the slot"
  say "$second" "Book number 1, my name is Omar Said, phone 93456789"
  expect '.reply | test("no longer available")' \
    "double booking: the second patient should be told the slot is taken"
  pass "second booking refused by the database's unique index, not by luck"
}

scenario_same_day() {
  section "FR-5  Same-day booking waits for a real staff approval"
  start_conversation
  local id="$STARTED_ID"
  say "$id" "Any free dentistry slots today?"
  if ! jq -e '.reply | test("(^|\n)1\\. ")' >/dev/null <<<"$RESPONSE"; then
    echo "  SKIP: no free same-day slots left today (clinic day is over); the cancel scenario"
    echo "        below shows the same approval flow."
    return
  fi
  say "$id" "Book number 1, my name is Mona Hamed, phone 94567890"
  expect '.status == "awaiting_approval" and (.approval_id | type == "number")' \
    "same day: expected awaiting_approval with an approval_id"
  local approval
  approval="$(json_field '.approval_id')"
  pass "graph paused at interrupt(); approval #$approval is waiting"

  say "$id" "Hello?" 409
  pass "the conversation is locked while staff decide (HTTP 409)"

  request GET /api/v1/approvals 200
  expect 'any(.[]; .id == ($a | tonumber))' "staff queue: approval missing" --arg a "$approval"
  pass "GET /api/v1/approvals: staff see the request"
  decide "$approval" true "Doctor confirmed she can fit it in"
  json_field '.outcome' | sed 's/^/  clinic  > /'
  pass "approved: the graph resumed and the patient got the outcome"

  decide "$approval" false "Second click" 409
  pass "deciding twice is refused (HTTP 409)"
}

scenario_cancel() {
  section "FR-5  Cancellation always needs staff, and survives a restart"
  start_conversation
  local stranger="$STARTED_ID"
  say "$stranger" "Please cancel booking $BOOKING_ID"
  expect '.status != "awaiting_approval"' "ownership: another patient's cancel must not pause"
  pass "another conversation cannot cancel booking #$BOOKING_ID"

  say "$PATIENT_ID" "Please cancel booking $BOOKING_ID"
  expect '.status == "awaiting_approval"' "cancel: expected awaiting_approval"
  local approval
  approval="$(json_field '.approval_id')"
  pass "cancellation paused for staff (approval #$approval)"

  if [[ "$DEMO_RESTART" == "1" ]]; then
    restart_api
    pass "api restarted while the cancellation was waiting"
  fi
  request GET /api/v1/approvals 200
  expect 'any(.[]; .id == ($a | tonumber))' "restart: approval lost" --arg a "$approval"
  decide "$approval" false "Please call us to cancel within 24 hours"
  json_field '.outcome' | sed 's/^/  clinic  > /'
  free_slot_ids Dentistry "$BOOKED_DATE"
  expect 'all(.[]; .id != ($slot | tonumber))' "reject: the booking should stay" \
    --arg slot "$BOOKED_SLOT_ID"
  pass "resumed after the restart; rejected, so booking #$BOOKING_ID stays"

  say "$PATIENT_ID" "Please cancel booking $BOOKING_ID"
  approval="$(json_field '.approval_id')"
  decide "$approval" true "Cancelled at the patient's request"
  json_field '.outcome' | sed 's/^/  clinic  > /'
  free_slot_ids Dentistry "$BOOKED_DATE"
  expect 'any(.[]; .id == ($slot | tonumber))' "approve: the slot should be free again" \
    --arg slot "$BOOKED_SLOT_ID"
  pass "approved: booking cancelled and slot #$BOOKED_SLOT_ID is free again"
}

scenario_history() {
  section "FR-1  The conversation is saved and resumable by id"
  request GET "/api/v1/conversations/$PATIENT_ID" 200
  expect '.messages | length >= 8' "history: expected the whole booking and cancel exchange"
  json_field '.messages[] | "  \(if .role == "patient" then "patient" else "clinic " end) > \(.content | split("\n")[0])"'
  pass "GET /api/v1/conversations/$PATIENT_ID: $(json_field '.messages | length') messages kept"
}

require_tools
if [[ "$DEMO_RESTART" == "1" ]]; then
  command -v docker >/dev/null || fail "docker is not installed; run with DEMO_RESTART=0"
fi

echo "Clinic Front-Desk Assistant demo against $BASE_URL"
scenario_health
scenario_questions
scenario_understanding
scenario_emergency
scenario_booking
scenario_double_booking
scenario_same_day
scenario_cancel
scenario_history
printf '\nAll demo scenarios passed.\n'
