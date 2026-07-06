#!/usr/bin/env python3
"""Pre-build resolver: Obsidian vault -> MkDocs docs tree.

Reads a folder of Obsidian-flavored Markdown, then:

1. Builds a link-target registry from every page's filename stem AND its
   frontmatter `aliases:` list (case-insensitive, like Obsidian).
2. Rewrites `[[Target]]`, `[[Target|display]]` and `[[Target#Heading]]` into
   standard relative Markdown links that MkDocs can validate.
3. Slugifies output filenames ("Raft consensus.md" -> "raft-consensus.md") so
   the served URLs are clean (/concepts/raft-consensus/).
4. Appends a "Backlinks" section to every page that is linked from elsewhere.
5. Prints a WARNING for every unresolved wikilink (visible in the build log);
   with --strict (or STRICT_LINKS=1) unresolved links fail the build.

Frontmatter is preserved in the output; MkDocs consumes it as page metadata
and never renders it into the page body.

Usage: resolve_links.py SRC_DIR OUT_DIR [--strict]
"""

import os
import re
import sys
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# [[target]] | [[target|display]] | [[target#heading]] | [[target#heading|display]]
WIKILINK_RE = re.compile(r"\[\[([^\]\[|#]+)(?:#([^\]\[|]+))?(?:\|([^\]\[]+))?\]\]")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")


def slugify(name):
    """Filename stem -> URL-friendly slug. Keeps letters/digits/_/-, spaces -> '-'."""
    slug = name.strip().lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9_-]+", "-", slug)
    return re.sub(r"-{2,}", "-", slug).strip("-")


def anchor_slug(heading):
    """Match python-markdown's toc slugification for #Heading anchors."""
    return re.sub(r"[\s]+", "-", re.sub(r"[^\w\s-]", "", heading.strip().lower()))


def parse_page(path, src_root):
    raw = path.read_text(encoding="utf-8")
    meta, body = {}, raw
    m = FRONTMATTER_RE.match(raw)
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as exc:
            print("WARNING: bad frontmatter in {}: {}".format(path, exc))
    rel = path.relative_to(src_root)
    out_rel = rel.parent / (slugify(path.stem) + ".md")
    return {
        "src": path,
        "rel": rel,
        "out_rel": Path(*[p for p in out_rel.parts]),
        "raw": raw,
        "meta": meta if isinstance(meta, dict) else {},
        "title": path.stem,
    }


def build_registry(pages):
    """Map lowercase target name -> page, from filename stems and aliases."""
    registry = {}

    def register(name, page):
        key = str(name).strip().lower()
        if not key:
            return
        existing = registry.get(key)
        if existing is not None and existing is not page:
            print(
                "WARNING: duplicate link target '{}' ({} vs {}); keeping {}".format(
                    name, existing["rel"], page["rel"], existing["rel"]
                )
            )
            return
        registry[key] = page

    for page in pages:
        register(page["src"].stem, page)
    for page in pages:
        aliases = page["meta"].get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        for alias in aliases:
            register(alias, page)
    return registry


def normalize_lists(text):
    """Insert the blank line python-markdown needs before a list that directly
    follows a paragraph (Obsidian doesn't require one, so vaults omit it).
    Leaves frontmatter, fenced code blocks, consecutive list items, and
    indented continuation lines alone."""
    m = FRONTMATTER_RE.match(text)
    head, body = (text[: m.end()], text[m.end():]) if m else ("", text)

    out = []
    in_fence = False
    for line in body.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        elif (
            not in_fence
            and LIST_ITEM_RE.match(line)
            and out
            and out[-1].strip()
            and not out[-1][0].isspace()      # continuation lines are indented
            and not LIST_ITEM_RE.match(out[-1])
        ):
            out.append("")
        out.append(line)
    return head + "\n".join(out)


def relative_url(from_page, to_page, anchor=None):
    rel = os.path.relpath(str(to_page["out_rel"]), str(from_page["out_rel"].parent))
    url = rel.replace(os.sep, "/")
    if anchor:
        url += "#" + anchor_slug(anchor)
    return url


def main():
    args = [a for a in sys.argv[1:] if a != "--strict"]
    strict = "--strict" in sys.argv[1:] or os.environ.get("STRICT_LINKS") == "1"
    if len(args) != 2:
        sys.exit(__doc__)
    src_root, out_root = Path(args[0]), Path(args[1])

    md_files = sorted(
        p for p in src_root.rglob("*.md")
        if not any(part.startswith(".") for part in p.relative_to(src_root).parts)
    )
    if not md_files:
        sys.exit("ERROR: no .md files found under {}".format(src_root))

    pages = [parse_page(p, src_root) for p in md_files]
    registry = build_registry(pages)
    backlinks = {}  # out_rel of target -> set of source pages
    unresolved = []

    def render(page):
        def sub(match):
            target, anchor, display = match.groups()
            text = (display or target).strip()
            hit = registry.get(target.strip().lower())
            if hit is None:
                unresolved.append((page["rel"], match.group(0)))
                return text  # never emit literal [[...]]
            if hit is not page:
                backlinks.setdefault(str(hit["out_rel"]), {})[str(page["out_rel"])] = page
            return "[{}]({})".format(text, relative_url(page, hit, anchor))

        return WIKILINK_RE.sub(sub, page["raw"])

    rendered = {str(p["out_rel"]): normalize_lists(render(p)) for p in pages}

    for page in pages:
        body = rendered[str(page["out_rel"])]
        sources = backlinks.get(str(page["out_rel"]), {})
        if sources:
            lines = sorted(
                "- [{}]({})".format(src["title"], relative_url(page, src))
                for src in sources.values()
            )
            body = body.rstrip() + "\n\n## Backlinks\n\n" + "\n".join(lines) + "\n"
        out_path = out_root / page["out_rel"]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body, encoding="utf-8")

    for rel, link in unresolved:
        print("WARNING: unresolved wikilink {} in {}".format(link, rel))
    print(
        "resolve_links: {} pages, {} link targets, {} unresolved wikilinks".format(
            len(pages), len(registry), len(unresolved)
        )
    )
    if unresolved and strict:
        sys.exit("ERROR: unresolved wikilinks with --strict")


if __name__ == "__main__":
    main()
