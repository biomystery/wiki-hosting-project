# Obsidian wiki → static site (Docker)

Builds an Obsidian-flavored Markdown vault into a static, searchable website and
serves it with nginx — one multi-stage `Dockerfile`, no manual steps.

> **Scope note:** authentication (oauth2-proxy / Okta) is handled **outside this
> repo** by the operator. This image serves the rendered wiki over plain HTTP on
> port 80 and must sit **behind** that auth proxy — never publish its port to the
> internet directly. The content is private.

## Quickstart

```sh
docker build -t wiki .
docker run --rm -p 127.0.0.1:8090:80 wiki   # bind to localhost only
open http://127.0.0.1:8090/
```

Default content is the `sample-wiki/` fixture.

## Static-HTML export (serve from your own nginx)

If you already run a web server and just want the rendered files — no wiki
container — export the built site to a folder:

```sh
./build-site.sh /path/to/vault /path/to/output-dir
```

Mount the output dir into your nginx (e.g. `- ./wiki_html:/wiki/:ro`) and add a
`location /wiki/ { alias /wiki/; index index.html; }` block behind whatever
auth you use (`auth_request`, oauth2-proxy, ...). MkDocs output is fully
relative, so any path prefix works. Re-run the script after content changes —
nginx picks up the new files with no restart.

## Swapping in the real vault

The vault is a named build context — **one path, no code change**:

```sh
docker buildx build --load --build-context vault=/path/to/real-vault -t wiki .
```

(`vault=` overrides the `FROM scratch AS vault` stage in the `Dockerfile` that
defaults to `sample-wiki/`.) Any folder of the same shape works: type-based
subfolders, YAML frontmatter with `aliases:`, `[[wikilinks]]`, filenames with
spaces. Nothing about the fixture's specific pages is hard-coded.

**Rebuild on content change:** content is baked at build time, so re-run
`docker build` (and restart the container) after editing the vault. Layer
caching makes this a few seconds.

## What the build does

```
vault (Obsidian .md) ──resolver──▶ docs/ (standard Markdown) ──mkdocs──▶ site/ (static HTML) ──▶ nginx
```

1. **`resolver/resolve_links.py`** (pre-build, ~150 lines): builds a link-target
   registry from every page's filename **and** its frontmatter `aliases:`, then
   rewrites `[[Target]]`, `[[Target|display]]`, `[[Target#Heading]]` into
   standard relative Markdown links. It slugifies paths (`Raft consensus.md` →
   `/concepts/raft-consensus/`), appends a **Backlinks** section to every linked
   page, and prints a `WARNING` per unresolved wikilink in the build log —
   `--strict` / `STRICT_LINKS=1` turns those into build failures.
2. **MkDocs + Material** builds the site with `--strict` (any broken resulting
   link fails the image build), client-side **full-text search** included, and
   navigation auto-generated from the type-based folders (`people/`, `concepts/`,
   `refs/`, `projects/`, `experiments/`). `index.md` is the landing page.
   Frontmatter is consumed as page metadata, never rendered. No Google Fonts or
   other external requests — the site is fully self-contained.

Why a custom resolver instead of `mkdocs-roamlinks` / `ezlinks` /
`obsidian-bridge`: none of them resolve frontmatter **aliases** (`[[Raft]]` →
`Raft consensus.md`), which is a hard requirement here. One small, tested script
replaces plugin + patch-script.

## Tests

```sh
python3 resolver/test_resolver.py
```

Copies the fixture, adds alias-only links (`[[Raft]]`, `[[Ada]]`,
`[[Meridian KV]]`) and a deliberately broken link, then asserts: alias and
canonical links resolve to the same page, no literal `[[...]]` survives,
the broken link is reported (and fails `--strict`).

## Layout

```
Dockerfile                 multi-stage: vault → resolver → mkdocs → nginx
mkdocs.yml                 Material theme, search, strict link validation
requirements.txt           mkdocs-material, PyYAML
resolver/resolve_links.py  wikilink + alias resolver (see above)
resolver/test_resolver.py  proof against the fixture
sample-wiki/               synthetic Obsidian vault (default content / fixture)
```
