#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OWNER_REPO_DEFAULT="$(git -C "$ROOT_DIR" remote get-url origin 2>/dev/null || true)"

OWNER=""
REPO=""
BRANCH="main"
APPLY=0
OUT_JSON="$ROOT_DIR/docs/baseline/evidence/branch_protection_status.json"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/branch_protection_gate.sh [options]

Options:
  --owner OWNER          GitHub owner/org (default inferred from origin remote)
  --repo REPO            GitHub repo name (default inferred from origin remote)
  --branch BRANCH        Branch to check/apply protection on (default: main)
  --apply                Apply recommended protection policy before verifying
  --out-json PATH        Output JSON path (default: docs/baseline/evidence/branch_protection_status.json)
  --help                 Show usage
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --owner)
      OWNER="$2"
      shift 2
      ;;
    --repo)
      REPO="$2"
      shift 2
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    --apply)
      APPLY=1
      shift
      ;;
    --out-json)
      OUT_JSON="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$OWNER" || -z "$REPO" ]]; then
  if [[ "$OWNER_REPO_DEFAULT" =~ github\.com[:/]([^/]+)/([^/.]+)(\.git)?$ ]]; then
    OWNER="${OWNER:-${BASH_REMATCH[1]}}"
    REPO="${REPO:-${BASH_REMATCH[2]}}"
  fi
fi

if [[ -z "$OWNER" || -z "$REPO" ]]; then
  echo "Unable to resolve owner/repo. Pass --owner and --repo explicitly." >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required but not installed." >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh CLI is not authenticated. Run: gh auth login" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT_JSON")"

api_path="repos/${OWNER}/${REPO}/branches/${BRANCH}/protection"

apply_policy() {
  local payload
  payload="$(mktemp)"
  cat >"$payload" <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON

  if ! gh api --method PUT "$api_path" --input "$payload" >/dev/null 2>"/tmp/nexra_bp_apply.err"; then
    cat "/tmp/nexra_bp_apply.err" >&2
    rm -f "$payload"
    return 1
  fi

  rm -f "$payload"
  return 0
}

if [[ "$APPLY" == "1" ]]; then
  echo "[branch-protection] applying recommended policy to ${OWNER}/${REPO}:${BRANCH}"
  if ! apply_policy; then
    echo "[branch-protection] apply failed" >&2
  fi
fi

status_file="$(mktemp)"
if ! gh api "$api_path" >"$status_file" 2>"/tmp/nexra_bp_get.err"; then
  err="$(cat /tmp/nexra_bp_get.err)"
  python3 - <<'PY' "$OUT_JSON" "$OWNER" "$REPO" "$BRANCH" "$err"
import json
import sys
from datetime import datetime, timezone

out, owner, repo, branch, err = sys.argv[1:6]
lower = err.lower()
if "upgrade to github pro" in lower or "http 403" in lower:
    status = "blocked_by_plan"
    pass_gate = False
elif "http 404" in lower:
    status = "not_configured"
    pass_gate = False
else:
    status = "unknown_error"
    pass_gate = False

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "owner": owner,
    "repo": repo,
    "branch": branch,
    "status": status,
    "pass": pass_gate,
    "error": err.strip(),
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, sort_keys=True)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  rm -f "$status_file"
  exit 1
fi

python3 - <<'PY' "$status_file" "$OUT_JSON" "$OWNER" "$REPO" "$BRANCH"
import json
import sys
from datetime import datetime, timezone

status_path, out, owner, repo, branch = sys.argv[1:6]
with open(status_path, encoding="utf-8") as f:
    raw = json.load(f)

review_cfg = raw.get("required_pull_request_reviews") or {}
required_reviews = int(review_cfg.get("required_approving_review_count") or 0)
linear = bool(raw.get("required_linear_history", {}).get("enabled", False))
conversation = bool(raw.get("required_conversation_resolution", {}).get("enabled", False))
force_pushes = bool(raw.get("allow_force_pushes", {}).get("enabled", False))
deletions = bool(raw.get("allow_deletions", {}).get("enabled", False))

pass_gate = (
    required_reviews >= 1
    and linear
    and conversation
    and not force_pushes
    and not deletions
)

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "owner": owner,
    "repo": repo,
    "branch": branch,
    "status": "configured" if pass_gate else "configured_but_incomplete",
    "pass": pass_gate,
    "required_approving_review_count": required_reviews,
    "required_linear_history": linear,
    "required_conversation_resolution": conversation,
    "allow_force_pushes": force_pushes,
    "allow_deletions": deletions,
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, sort_keys=True)

print(json.dumps(payload, indent=2, sort_keys=True))
PY

rm -f "$status_file"
