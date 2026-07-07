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
        assert len(graph["nodes"]) == 14, titles
        raft = titles.index("Raft consensus")
        exercise = titles.index("Alias exercise")
        assert [exercise, raft] in graph["edges"], "alias link missing from graph"
        assert graph["nodes"][raft]["url"] == "concepts/raft-consensus/"
        assert graph["nodes"][raft]["type"] == "concept"
        assert (out / "graph.md").exists()

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
