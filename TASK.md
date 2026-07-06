# TASK — Host an Obsidian-style LLM-wiki as a private website

You are being handed a **greenfield project**. Build a self-contained, containerized
service that serves a folder of Obsidian-flavored Markdown notes as a browsable website,
gated behind **Okta SSO**, deployable with **Docker Compose**.

A synthetic sample wiki is provided under `sample-wiki/` — use it as your test fixture and
as the default content the site serves. **Do not** assume any particular real content; the
real vault has the same *structure* but different (private) text, so everything you build
must be driven by the folder structure and Markdown conventions below, not by specific pages.

---

## 1. What the source content looks like

The wiki is a plain folder of `.md` files (an Obsidian vault). Structural conventions you
MUST support:

- **Obsidian wikilinks:** `[[Page Name]]` and `[[Page Name|display text]]`. These are the
  primary link style — there are hundreds of them. Rendering them as literal `[[...]]` text
  is a failure. They must resolve to the correct page's URL.
- **Aliases:** pages carry YAML frontmatter with an `aliases:` list. A wikilink written as
  `[[Raft]]` must resolve to the page whose frontmatter includes `Raft` as an alias, even if
  the filename is `Raft consensus.md`. Alias resolution is a hard requirement, not nice-to-have.
- **Frontmatter:** every page starts with a YAML block: `type:` (one of
  person/concept/reference/project/experiment/MOC), `aliases:`, `tags:`, plus `created:` /
  `updated:` timestamps. Do not render the raw frontmatter into the page body.
- **Type-based folders:** `people/`, `concepts/`, `refs/`, `projects/`, `experiments/`.
- **Two special files:** `index.md` (a catalog / table of contents — should be the site
  landing page or clearly linked from it) and `log.md` (an append-only changelog).
- **MOC pages** (Maps of Content): hub pages that link out to many others (e.g.
  `Meridian MOC.md`). Nothing special structurally — just heavily-linked pages.
- Filenames contain **spaces** (e.g. `Raft consensus.md`). URL/link resolution must handle
  spaces and the `.md` → clean-URL mapping.
- Assume **no binary attachments / embedded images** in scope (the fixture has none). Don't
  spend effort on image/attachment embedding.

## 2. Required capabilities of the site

1. Renders every `.md` page to HTML with working navigation between pages.
2. **Wikilinks and aliases resolve** to the right pages (see §1). Broken/unresolved links
   should be visible in the build log, not silently swallowed.
3. **Full-text search** across all pages (client-side is fine).
4. **Navigation** reflecting the type-based folders, plus **backlinks** on each page if the
   chosen tool supports it (nice-to-have, not blocking).
5. Reproducible build: content in → static site out, no manual steps.

## 3. Recommended stack (justify any deviation)

- **MkDocs + Material for MkDocs** as the site generator. It has excellent built-in search,
  navigation, and theming, and ships cleanly in a container.
- **Wikilink support:** add a plugin that resolves Obsidian `[[wikilinks]]` — e.g.
  `mkdocs-roamlinks-plugin` or `mkdocs-ezlinks-plugin` or `mkdocs-obsidian-bridge`. **You must
  verify alias resolution works**; if the off-the-shelf plugin can't resolve `aliases:`,
  either configure it, pick another, or add a small pre-build script that rewrites
  `[[alias]]` → `[[Canonical Page]]` using each page's frontmatter. Whatever you choose,
  prove it against the fixture (see Acceptance).
- **Auth:** `oauth2-proxy` configured as an **OIDC** client against **Okta**, running as the
  front door in reverse-proxy mode (`--upstream` → the MkDocs container). All requests hit
  oauth2-proxy first; unauthenticated users get redirected to Okta; after login, requests are
  proxied to the site. Restrict access to an Okta group/app assignment.
- **Compose topology (target):**
  - `wiki` — builds the site (multi-stage: `mkdocs build` in a Python stage, then serve the
    static `site/` from nginx). Not exposed to the host directly.
  - `oauth2-proxy` — the only published port; OIDC against Okta; upstream = `wiki`.
- **Secrets/config:** Okta client id/secret, issuer URL, cookie secret, allowed
  group/emails — all via environment variables / `.env`, never hard-coded. Provide a
  `.env.example` with every required variable documented and dummy values.

Alternative auth path if oauth2-proxy proves awkward: nginx `auth_request` → oauth2-proxy, or
Caddy `forward_auth`. Pick one, keep it to two services if you can.

## 4. Hard constraints

- **The real content is confidential.** Design for **private, authenticated access only** —
  there must be **no unauthenticated path** to any page (verify: hitting a deep page URL while
  logged out redirects to Okta, does not leak content). No public/anonymous mode, no
  "publish to the internet" service.
- Everything runs locally via `docker compose up`. No dependency on a specific cloud.
- Content folder is a **mounted input**, not baked assumptions — the operator swaps
  `sample-wiki/` for the real vault by changing one path/volume. Document that swap.
- Don't commit real secrets or any content beyond the synthetic fixture.

## 5. Deliverables

1. `docker-compose.yml` — the two-service topology above.
2. `Dockerfile` (multi-stage build for the site) and `mkdocs.yml`.
3. Wikilink/alias resolution wired and **proven** (plugin config and/or a pre-build script).
4. `oauth2-proxy` configuration for Okta OIDC.
5. `.env.example` documenting every variable, plus a short **Okta setup checklist** (what to
   create in the Okta admin console: OIDC web app, redirect URI
   `/<oauth2-proxy path>/callback`, group assignment, which values map to which env vars).
6. `README.md`: quickstart (`cp .env.example .env` → fill → `docker compose up`), how to swap
   in the real vault, how to rebuild on content change, and the architecture in a few lines.
7. The `sample-wiki/` fixture, served by default.

## 6. Acceptance criteria (Fable 5 should self-verify before finishing)

- `docker compose up` yields a running site reachable through oauth2-proxy.
- **Logged-out** request to a deep page (e.g. `/concepts/raft-consensus/`) → redirected to
  Okta login, **no content leaks**.
- After auth, the site renders; **search works**.
- **Wikilink check:** `[[Raft consensus]]` and the alias form `[[Raft]]` (used in the fixture)
  both resolve to the same rendered page; navigate the rendered links and confirm no literal
  `[[...]]` appears in output and no dead links in the build log.
- Swapping the content volume to a different folder of the same shape requires **no code
  change** — only a path change. State this explicitly and show where.
- Verify end-to-end by actually driving it (curl the redirect, load pages), not just by
  reading config.

## 7. Notes / good judgment

- Keep it to the smallest number of moving parts that satisfies the constraints.
- Prefer configuration over custom code; if you write a pre-build wikilink/alias resolver,
  keep it small, documented, and covered by the fixture.
- If a plugin or oauth2-proxy option doesn't behave as its docs claim, say so and show the
  workaround you used — don't leave a silently-broken feature.
