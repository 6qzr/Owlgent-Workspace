#!/usr/bin/env bash
# One-off GitHub setup for the team repo. Run by the team lead with `gh` logged in.
#   bash scripts/setup_github.sh labels       # create the backlog labels
#   bash scripts/setup_github.sh protect      # protect main (run AFTER the first CI run on a PR)
set -euo pipefail

REPO="${REPO:-6qzr/Owlgent-Workspace}"

labels() {
  # name|color|description
  local defs=(
    "story|1d76db|User story"
    "task|c5def5|1-3 hour task of a story"
    "spike|fbca04|Time-boxed research (no points)"
    "po-decision|d93f0b|Product Owner decision recorded"
    "epic:platform|5319e7|Repo, CI, tooling"
    "epic:conversation|5319e7|Conversations, checkpoints, intent routing"
    "epic:safety|5319e7|Emergency handling, no diagnosis"
    "epic:knowledge|5319e7|Clinic documents, RAG"
    "epic:appointments|5319e7|Slots and bookings"
    "epic:approvals|5319e7|Staff approval, human in the loop"
    "epic:ops|5319e7|Compose, health, release, VM"
    "pts:1|ededed|Story points"
    "pts:2|ededed|Story points"
    "pts:3|ededed|Story points"
    "pts:5|ededed|Story points"
    "pts:8|ededed|Story points"
    "should|bfd4f2|Should: only after every Must is merged"
    "could|bfd4f2|Could: only if time allows"
  )
  for d in "${defs[@]}"; do
    IFS='|' read -r name color desc <<<"$d"
    gh label create "$name" --repo "$REPO" --color "$color" --description "$desc" --force
  done
}

protect() {
  # 2 approvals, stale approvals dismissed, code owners, 4 required checks, up to date,
  # linear history (squash only), no force push or deletion.
  gh api -X PUT "repos/$REPO/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint", "typecheck", "test", "compose-up"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 2,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
  # Squash merge only, auto-delete merged branches.
  gh api -X PATCH "repos/$REPO" \
    -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false \
    -F delete_branch_on_merge=true >/dev/null
  echo "main is protected."
}

case "${1:-}" in
  labels) labels ;;
  protect) protect ;;
  *) echo "usage: $0 labels|protect" >&2; exit 2 ;;
esac
