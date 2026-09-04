#!/usr/bin/env bash
set -euo pipefail

REMOTE="${1:-origin}"
BASE_REF="${BASE_REF:-$REMOTE/main}"
TARGET_BRANCH="${TARGET_BRANCH:-develop}"

git fetch "$REMOTE" main "$TARGET_BRANCH"

if ! git merge-base --is-ancestor "$REMOTE/$TARGET_BRANCH" "$BASE_REF"; then
  echo "[EXPERIMENT_BRANCH_SYNC_ERROR] $REMOTE/$TARGET_BRANCH is not a fast-forward ancestor of $BASE_REF" >&2
  echo "Resolve divergence before overwriting the experiment branch." >&2
  exit 1
fi

if [ "$(git branch --show-current)" = "$TARGET_BRANCH" ]; then
  echo "[EXPERIMENT_BRANCH_SYNC_ERROR] checkout a different branch before running this script" >&2
  exit 1
fi

target_sha="$(git rev-parse "$BASE_REF")"
git branch -f "$TARGET_BRANCH" "$target_sha"
git push "$REMOTE" "$target_sha:refs/heads/$TARGET_BRANCH"

echo "[EXPERIMENT_BRANCH_SYNC_OK] $TARGET_BRANCH -> $target_sha (base=$BASE_REF)"
