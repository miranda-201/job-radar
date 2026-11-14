#!/usr/bin/env bash
# End-to-end smoke test against a running stack (docker compose up).
# Walks the whole event path: browser gateway -> tracker auth -> scraper (JWT) -> live
# career pages -> RabbitMQ -> tracker consumer -> PostgreSQL -> jobs API -> Kanban board.
set -euo pipefail

BASE="${BASE_URL:-http://localhost:3000}"
EMAIL="smoke-$(date +%s)@example.edu"
step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

step "gateway is serving the SPA"
curl -fsS "$BASE/" | grep -q '<div id="root">' || fail "SPA not served"

step "register a user via tracker-service"
TOKEN=$(curl -fsS -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"displayName\":\"Smoke Test\",\"password\":\"smoke-test-pw\"}" | jq -r .token)
[[ -n "$TOKEN" && "$TOKEN" != null ]] || fail "no token"
AUTH=(-H "Authorization: Bearer $TOKEN")

step "scraper-service accepts the tracker-issued JWT"
curl -fsS "${AUTH[@]}" "$BASE/api/scraper/targets" | jq -e 'length > 0' >/dev/null || fail "no targets"
curl -s -o /dev/null -w '%{http_code}' "$BASE/api/scraper/targets" | grep -q 401 || fail "scraper allowed anonymous access"

step "trigger a sweep of live career pages"
curl -fsS -X POST "${AUTH[@]}" "$BASE/api/scraper/scrape" \
  | jq -r '.results[] | "  \(.target_id): \(.matched) matched, \(.new) new\(if .error then " ERROR " + .error else "" end)"'

step "postings flow through RabbitMQ into PostgreSQL"
for i in $(seq 1 30); do
  TOTAL=$(curl -fsS "${AUTH[@]}" "$BASE/api/jobs?size=1" | jq .totalItems)
  [[ "$TOTAL" -gt 0 ]] && break
  sleep 2
done
[[ "$TOTAL" -gt 0 ]] || fail "no jobs ingested"
echo "  $TOTAL postings ingested"

step "track a posting and move it across the board"
JOB_ID=$(curl -fsS "${AUTH[@]}" "$BASE/api/jobs?size=1" | jq '.items[0].id')
APP_ID=$(curl -fsS -X POST "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d "{\"jobId\":$JOB_ID}" "$BASE/api/applications" | jq .id)
curl -fsS -X PUT "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d '{"status":"INTERVIEWING","position":0}' "$BASE/api/applications/$APP_ID/move" \
  | jq -e '.status == "INTERVIEWING" and .appliedAt != null' >/dev/null || fail "move failed"
curl -fsS "${AUTH[@]}" "$BASE/api/applications/stats" | jq -e '.byStatus.INTERVIEWING == 1' >/dev/null

printf '\n\033[32mSmoke test passed.\033[0m\n'
