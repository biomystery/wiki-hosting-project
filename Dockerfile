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
COPY --from=vault / vault/

# resolve_links.py rewrites [[wikilinks]] (incl. frontmatter aliases) to real
# relative links and prints a WARNING per unresolved link. `mkdocs build
# --strict` then fails the image build on any broken resulting link, so link
# rot is visible here, never silently swallowed.
RUN python resolver/resolve_links.py vault docs \
 && mkdocs build --strict

# --- Stage 2: serve the static site -----------------------------------------
FROM nginx:1.27-alpine
COPY --from=build /build/site /usr/share/nginx/html
EXPOSE 80
