# Multi-stage build: Obsidian vault -> static MkDocs site -> nginx.
#
# The vault is a swappable named build context. Default is ./sample-wiki
# (the `vault` stage below). To build against a different vault — no code
# change, one path:
#
#   docker buildx build --load --build-context vault=/path/to/real-vault -t wiki .
#
# BuildKit lets --build-context override the same-named stage. (Plain
# `docker build` works for the default; --build-context needs buildx.)

FROM scratch AS vault
COPY sample-wiki/ /

# --- Stage 1: resolve wikilinks + build the static site --------------------
FROM python:3.12-slim AS build
WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY resolver/resolve_links.py resolver/
COPY mkdocs.yml .
COPY theme/ theme/
COPY --from=vault / vault/

# Site title shown in the header; override per deployment:
#   docker buildx build --build-arg SITE_NAME="Team Wiki" ...
ARG SITE_NAME=Wiki
ENV WIKI_SITE_NAME=$SITE_NAME

# resolve_links.py rewrites [[wikilinks]] (incl. frontmatter aliases) to real
# relative links and prints a WARNING per unresolved link. `mkdocs build
# --strict` then fails the image build on any broken resulting link, so link
# rot is visible here, never silently swallowed.
RUN python resolver/resolve_links.py vault docs \
 && cp -r theme docs/_theme \
 && mkdocs build --strict

# --- Optional target: export the static HTML only ---------------------------
# For serving from an existing nginx (no wiki container), write site/ to a
# local folder:   ./build-site.sh /path/to/vault /path/to/output
FROM scratch AS site
COPY --from=build /build/site /

# --- Default target: serve the static site ----------------------------------
FROM nginx:1.27-alpine
COPY --from=build /build/site /usr/share/nginx/html
EXPOSE 80
