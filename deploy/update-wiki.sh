#!/usr/bin/env sh
# Pull the wiki content repo and rebuild the static site — but only when the
# content actually changed. Safe to run from cron (single-flight via a lock).
#
#   update-wiki.sh CONTENT_REPO_DIR VAULT_SUBDIR OUTPUT_DIR
#   update-wiki.sh --force ...            rebuild even without new commits
#
# Example (cron, every 10 min):
#   */10 * * * * /home/ubuntu/wiki-hosting-project/deploy/update-wiki.sh \
#       /home/ubuntu/sbt-kg-wiki wiki /home/ubuntu/data/sbt-kg-wiki \
#       >> /home/ubuntu/log/wiki-update.log 2>&1
set -eu

FORCE=0
[ "${1:-}" = "--force" ] && { FORCE=1; shift; }

REPO=${1:?usage: update-wiki.sh [--force] CONTENT_REPO_DIR VAULT_SUBDIR OUTPUT_DIR}
SUBDIR=${2:?usage: update-wiki.sh [--force] CONTENT_REPO_DIR VAULT_SUBDIR OUTPUT_DIR}
OUT=${3:?usage: update-wiki.sh [--force] CONTENT_REPO_DIR VAULT_SUBDIR OUTPUT_DIR}
HERE=$(cd "$(dirname "$0")/.." && pwd)

LOCK="$REPO/.wiki-update.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date -u +%FT%TZ) another update is running (rm -rf $LOCK if stale); skipping"
  exit 0
fi
trap 'rmdir "$LOCK"' EXIT INT TERM

BEFORE=$(git -C "$REPO" rev-parse HEAD)
git -C "$REPO" pull --ff-only --quiet
AFTER=$(git -C "$REPO" rev-parse HEAD)

if [ "$BEFORE" = "$AFTER" ] && [ "$FORCE" = "0" ]; then
  echo "$(date -u +%FT%TZ) no content change ($AFTER); nothing to do"
  exit 0
fi

echo "$(date -u +%FT%TZ) rebuilding: $BEFORE -> $AFTER"
"$HERE/build-site.sh" "$REPO/$SUBDIR" "$OUT"
echo "$(date -u +%FT%TZ) done"
