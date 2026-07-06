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

docker buildx build \
  --target site \
  --output "type=local,dest=$OUT" \
  --build-context "vault=$VAULT" \
  "$(cd "$(dirname "$0")" && pwd)"

echo "Static site written to: $OUT"
