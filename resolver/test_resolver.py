#!/usr/bin/env python3
"""Prove wikilink/alias resolution against the fixture (run: python3 resolver/test_resolver.py).

Copies sample-wiki/ to a temp dir, adds a page exercising alias-only links
([[Raft]], [[Ada]], [[Meridian KV]]) plus one intentionally-broken link, runs
the resolver, and asserts:
  1. [[Raft consensus]] and alias [[Raft]] resolve to the SAME page URL.
  2. Other frontmatter aliases resolve correctly.
  3. No literal [[...]] survives in output.
  4. The broken link is reported (not silently swallowed) and not emitted raw.
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "sample-wiki"

EXTRA_PAGE = """---
type: concept
aliases: []
tags: [wiki]
created: 2026-01-01T00:00
updated: 2026-01-01T00:00
---
# Alias exercise

Canonical: [[Raft consensus]]. Alias: [[Raft]]. Person alias: [[Ada]].
Project alias: [[Meridian KV]]. Broken: [[Nonexistent page]].

Intro paragraph directly followed by a list
- glued one
- glued two

Already separated
- fine as is

```
code paragraph
- not a list item
```

> [!note]
> plain note body

> [!tldr] Key points
> alias with title and a [[Raft]] link

> [!warning]- Folded away
> hidden until clicked

> [!error]+ Shown but foldable
> expanded body

> [!todo]
> no direct Material type

> a plain blockquote, not a callout
"""


def main():
    tmp = Path(tempfile.mkdtemp(prefix="resolver-test-"))
    try:
        vault = tmp / "vault"
        shutil.copytree(FIXTURE, vault)
        (vault / "concepts" / "Alias exercise.md").write_text(EXTRA_PAGE, encoding="utf-8")
        (vault / "projects" / "index.md").write_text(
            "---\ntype: MOC\naliases: [projects index]\ntags: [wiki]\n"
            "created: 2026-01-01T00:00\nupdated: 2026-01-01T00:00\n---\n"
            "# Projects\n\nSee [[Meridian]].\n",
            encoding="utf-8",
        )

        out = tmp / "docs"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "resolver" / "resolve_links.py"), str(vault), str(out)],
            capture_output=True, text=True,
        )
        print(proc.stdout, end="")
        assert proc.returncode == 0, proc.stderr

        page = (out / "concepts" / "alias-exercise.md").read_text(encoding="utf-8")
        links = dict(re.findall(r"\[([^\]]+)\]\(([^)]+)\)", page))

        assert links["Raft consensus"] == "raft-consensus.md", links
        assert links["Raft"] == "raft-consensus.md", "alias [[Raft]] must hit the same page"
        assert links["Ada"] == "../people/ada-lindqvist.md", links
        assert links["Meridian KV"] == "../projects/meridian.md", links

        rendered = list(out.rglob("*.md"))
        assert not any("[[" in p.read_text(encoding="utf-8") for p in rendered), \
            "literal [[...]] leaked into output"
        assert "unresolved wikilink [[Nonexistent page]]" in proc.stdout, \
            "broken link was silently swallowed"
        assert "Nonexistent page" in page and "[[Nonexistent" not in page

        # list normalization: blank line inserted after a bare paragraph,
        # existing spacing and fenced code untouched, frontmatter untouched
        assert "followed by a list\n\n- glued one\n- glued two" in page, page
        assert "Already separated\n\n- fine as is" in page
        assert "code paragraph\n- not a list item" in page, "fence was modified"
        raft_out = (out / "concepts" / "raft-consensus.md").read_text(encoding="utf-8")
        assert raft_out.startswith("---\ntype: concept\naliases:\n  - Raft\n"), \
            "frontmatter was modified"

        # callouts -> Material admonitions
        assert "!!! note\n    plain note body" in page, page
        assert '!!! abstract "Key points"\n    alias with title and a [Raft](raft-consensus.md) link' in page
        assert '??? warning "Folded away"\n    hidden until clicked' in page
        assert '???+ danger "Shown but foldable"\n    expanded body' in page
        assert '!!! info "Todo"\n    no direct Material type' in page
        assert "> a plain blockquote, not a callout" in page, "plain quote was mangled"

        # graph emitted: every page is a node, edges follow wikilinks
        import json
        graph = json.loads((out / "graph.json").read_text(encoding="utf-8"))
        titles = [n["title"] for n in graph["nodes"]]
        assert len(graph["nodes"]) == 15, titles
        raft = titles.index("Raft consensus")
        exercise = titles.index("Alias exercise")
        assert sorted([exercise, raft]) in graph["edges"], "alias link missing from graph"
        assert graph["nodes"][raft]["url"] == "concepts/raft-consensus/"
        assert graph["nodes"][raft]["type"] == "concept"
        assert (out / "graph.md").exists()

        # nested index.md serves at its directory URL, not .../index/
        nested = titles.index("index" if titles.count("index") == 1 else "index")
        urls = {n["title"]: n["url"] for n in graph["nodes"]}
        assert "projects/" in [n["url"] for n in graph["nodes"]], urls
        assert not any(u.endswith("/index/") for u in urls.values()), urls

        # mutual wikilinks are deduped to one undirected edge
        assert len(graph["edges"]) == len({tuple(e) for e in graph["edges"]})
        assert all(e[0] < e[1] for e in graph["edges"]), "edges not canonicalized"

        # a vault owning a root graph.md keeps its page; graph.json still emitted
        own = tmp / "own-graph"
        (own / "concepts").mkdir(parents=True)
        (own / "graph.md").write_text("# My own graph page\n", encoding="utf-8")
        (own / "concepts" / "Solo.md").write_text("# Solo\n\nSee [[graph]].\n", encoding="utf-8")
        own_out = tmp / "own-out"
        own_run = subprocess.run(
            [sys.executable, str(ROOT / "resolver" / "resolve_links.py"), str(own), str(own_out)],
            capture_output=True, text=True,
        )
        assert own_run.returncode == 0, own_run.stderr
        assert "skipping generated graph page" in own_run.stdout, own_run.stdout
        own_page = (own_out / "graph.md").read_text(encoding="utf-8")
        assert own_page.startswith("# My own graph page"), own_page
        assert "wiki-graph-full" not in own_page, "vault's graph.md was clobbered"
        assert (own_out / "graph.json").exists()

        # strict mode must fail the build on the broken link
        strict = subprocess.run(
            [sys.executable, str(ROOT / "resolver" / "resolve_links.py"),
             str(vault), str(tmp / "docs-strict"), "--strict"],
            capture_output=True, text=True,
        )
        assert strict.returncode != 0, "--strict should fail on unresolved links"

        print("OK: alias resolution, broken-link reporting, and strict mode all verified")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
