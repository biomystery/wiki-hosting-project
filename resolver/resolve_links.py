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

import html
import json
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
CALLOUT_RE = re.compile(r"^>\s*\[!([A-Za-z]+)\]([+-]?)\s*(.*)$")

# Obsidian callout types and aliases (obsidian.md/help/callouts) -> Material
# admonition types. Material's set mirrors Obsidian's, so mapping is mostly
# identity plus the documented aliases. 'todo' has no Material equivalent and
# renders closest as 'info'.
CALLOUT_TYPES = {
    "note": "note",
    "abstract": "abstract", "summary": "abstract", "tldr": "abstract",
    "info": "info",
    "todo": "info",
    "tip": "tip", "hint": "tip", "important": "tip",
    "success": "success", "check": "success", "done": "success",
    "question": "question", "help": "question", "faq": "question",
    "warning": "warning", "caution": "warning", "attention": "warning",
    "failure": "failure", "fail": "failure", "missing": "failure",
    "danger": "danger", "error": "danger",
    "bug": "bug",
    "example": "example",
    "quote": "quote", "cite": "quote",
}


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


def convert_callouts(text):
    """Rewrite Obsidian callouts to Material admonitions.

    > [!type] Title      ->  !!! type "Title"        (plus 4-space body indent)
    > [!type]- Title     ->  ??? type "Title"        (foldable, collapsed)
    > [!type]+ Title     ->  ???+ type "Title"       (foldable, expanded)

    Aliases map per CALLOUT_TYPES; unknown types pass through (Material styles
    them like 'note'). Nested callouts convert recursively. Plain blockquotes
    and code fences are untouched.
    """
    m = FRONTMATTER_RE.match(text)
    head, body = (text[: m.end()], text[m.end():]) if m else ("", text)

    lines = body.split("\n")
    out = []
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if FENCE_RE.match(line):
            in_fence = not in_fence
        callout = None if in_fence else CALLOUT_RE.match(line)
        if callout is None:
            out.append(line)
            i += 1
            continue

        raw_type, fold, title = callout.groups()
        adm_type = CALLOUT_TYPES.get(raw_type.lower(), raw_type.lower())
        inner = []
        i += 1
        while i < len(lines) and lines[i].startswith(">"):
            stripped = lines[i][1:]
            if stripped.startswith(" "):
                stripped = stripped[1:]
            inner.append(stripped)
            i += 1

        marker = {"": "!!!", "-": "???", "+": "???+"}[fold]
        title = title.strip().replace('"', "'")
        if title:
            header = '{} {} "{}"'.format(marker, adm_type, title)
        elif adm_type != raw_type.lower():
            # keep the author's word as the visible title (e.g. [!tldr])
            header = '{} {} "{}"'.format(marker, adm_type, raw_type.capitalize())
        else:
            header = "{} {}".format(marker, adm_type)

        if out and out[-1].strip():
            out.append("")
        out.append(header)
        for inner_line in convert_callouts("\n".join(inner)).split("\n"):
            out.append(("    " + inner_line).rstrip())
        out.append("")
    return head + "\n".join(out)


def inject_frontmatter_url(text, meta):
    """Render the frontmatter `url:` field (string or list) as clickable
    links directly under the page title. Frontmatter itself is page metadata
    and never reaches the HTML, so without this the URL is silently lost."""
    urls = meta.get("url") or meta.get("URL")
    if not urls:
        return text
    if isinstance(urls, str):
        urls = [urls]
    anchors = []
    for u in urls:
        u = str(u).strip()
        if not u:
            continue
        href = u if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", u) else "https://" + u
        anchors.append(
            '<a href="{}" target="_blank" rel="noopener">{}</a>'.format(
                html.escape(href, quote=True), html.escape(u)
            )
        )
    if not anchors:
        return text
    block = '<p class="wiki-page-url">' + " · ".join(anchors) + "</p>"

    m = FRONTMATTER_RE.match(text)
    head, body = (text[: m.end()], text[m.end():]) if m else ("", text)
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# "):   # after the H1 title if the page has one
            lines.insert(i + 1, "\n" + block)
            return head + "\n".join(lines)
    return head + block + "\n\n" + body


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


GRAPH_PAGE = """# Graph

Every page is a node; wikilinks are edges. Drag nodes, scroll to zoom, click
to open a page.

<div id="wiki-graph-full"></div>
"""


def page_url(page):
    """Site-root-relative URL of a page under use_directory_urls."""
    rel = page["out_rel"].as_posix()
    if rel == "index.md" or rel.endswith("/index.md"):
        return rel[: -len("index.md")]   # index pages serve at their directory
    return rel[:-3] + "/"


def write_graph(pages, backlinks, out_root):
    """Emit graph.json (nodes + directed edges) and the full-graph page."""
    index = {str(p["out_rel"]): i for i, p in enumerate(pages)}
    # undirected + deduped: mutual links would otherwise double the drawn
    # line and the spring force between the pair
    edges = sorted(
        set(
            (min(index[src], index[target]), max(index[src], index[target]))
            for target, sources in backlinks.items()
            for src in sources
        )
    )
    edges = [list(e) for e in edges]
    nodes = [
        {
            "title": p["title"],
            "url": page_url(p),
            "type": str(p["meta"].get("type") or "").lower(),
        }
        for p in pages
    ]
    (out_root / "graph.json").write_text(
        json.dumps({"nodes": nodes, "edges": edges}), encoding="utf-8"
    )
    if any(p["out_rel"].as_posix() == "graph.md" for p in pages):
        print("WARNING: vault has its own root graph.md; skipping generated graph page")
        return
    (out_root / "graph.md").write_text(GRAPH_PAGE, encoding="utf-8")


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

    rendered = {
        str(p["out_rel"]): inject_frontmatter_url(
            normalize_lists(convert_callouts(render(p))), p["meta"]
        )
        for p in pages
    }

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

    write_graph(pages, backlinks, out_root)

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
