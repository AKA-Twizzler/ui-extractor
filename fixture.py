#!/usr/bin/env python3
"""The ground-truth fixture, parsed.

GROUND-TRUTH-TREE.md is Tristan's own reading of the 00:02:09 sidebar and is
the definition of done. This module turns it into rows so every run can be
scored against it instead of judged by eye.

Row: {name, kind ("folder"|"file"), chevron ("down"|"right"|None), depth}
"""
import re
import os

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "GROUND-TRUTH-TREE.md")

# guide lines and chevrons that sit left of the name in the fixture drawing
_PREFIX = "│˅˃ \t"          # │ ˅ ˃ space tab
_ROW = re.compile(
    r"^(?P<prefix>[│˅˃ \t]*)"
    r"(?P<name>\S.*?)\s{2,}"
    r"(?P<kind>folder|FILE)"
    r"(?:,\s*(?P<state>expanded|collapsed))?"
    r",?\s*depth\s+(?P<depth>\d+)\s*$"
)


def load(path=FIXTURE):
    rows = []
    inside = False
    for line in open(path, encoding="utf-8"):
        s = line.rstrip("\n")
        if s.strip().startswith("```"):
            inside = not inside
            continue
        if not inside:
            continue
        m = _ROW.match(s)
        if not m:
            continue
        prefix = m.group("prefix")
        chevron = None
        if "˅" in prefix:
            chevron = "down"
        elif "˃" in prefix:
            chevron = "right"
        rows.append({
            "name": m.group("name").strip(),
            "kind": "folder" if m.group("kind") == "folder" else "file",
            "chevron": chevron,
            "depth": int(m.group("depth")),
        })
    return rows


def norm(s):
    """Compare names forgivingly on punctuation and case, never on words."""
    t = s.lower()
    t = re.sub(r"[^a-z0-9&' ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


if __name__ == "__main__":
    rows = load()
    print(f"{len(rows)} fixture rows")
    for r in rows:
        print(f"  d{r['depth']} {r['kind']:6s} {str(r['chevron'] or '-'):5s} {r['name']}")
