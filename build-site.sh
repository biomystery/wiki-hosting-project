#!/usr/bin/env sh
# Convert an Obsidian vault to static HTML, no container left running.
#
#   ./build-site.sh /path/to/vault /path/to/output-dir
#
# Runs the same resolver + mkdocs pipeline as the full image, but exports the
# built site/ to OUTPUT-DIR so any existing web server can serve it.
set -eu

VAULT=${1:?usage: build-site.sh VAULT_DIR OUTPUT_DIR}
OUT=${2:?usage: build-site.sh VAULT_DIR OUTPUT_DIR}

# Clear the previous export so deleted wiki pages don't linger. Contents only —
# the dir itself stays, so an nginx bind mount on it remains valid. Refuses to
# wipe a folder that doesn't look like a previous export.
mkdir -p "$OUT"
OUT_ABS=$(cd "$OUT" && pwd)
[ "$OUT_ABS" != "/" ] || { echo "ERROR: refusing to use / as output" >&2; exit 1; }
if [ -e "$OUT_ABS/sitemap.xml" ] || [ -e "$OUT_ABS/index.html" ] || [ -z "$(ls -A "$OUT_ABS")" ]; then
  find "$OUT_ABS" -mindepth 1 -delete
else
  echo "ERROR: $OUT_ABS is not empty and doesn't look like a previous site export;" \
       "clear it yourself and re-run." >&2
  exit 1
fi

docker buildx build \
  --target site \
  --output "type=local,dest=$OUT" \
  --build-context "vault=$VAULT" \
  --build-arg "SITE_NAME=${SITE_NAME:-Wiki}" \
  "$(cd "$(dirname "$0")" && pwd)"

# nginx in a container typically runs as a non-root uid; make sure it can read
chmod -R a+rX "$OUT_ABS"

echo "Static site written to: $OUT"
