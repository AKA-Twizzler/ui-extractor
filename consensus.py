#!/usr/bin/env python3
"""Agree a name across several frames of the same pane.

A single frame gives one reading of a name; several frames give several, and
where they differ the majority is almost always right, because compression
noise is different in every frame while the text is not. This is the cheapest
accuracy left on the table and it costs nothing but more frames.

What it deliberately does NOT do is vote on structure. A tree legitimately
changes between moments — folders open, the view scrolls — so a disagreement
about depth is information, not error. Only the spelling of a name is voted.

The verdicts:
  agreed          every reading identical
  consensus       a clear majority, minority readings recorded
  ambiguous-glyph readings differ only where glyphs are undecidable
  disputed        no majority; nothing chosen, every reading kept

Run: python3 consensus.py <tree1.json> <tree2.json> ...
"""
import json
import re
import sys
from collections import Counter, defaultdict

from verify_names import HOMOGLYPHS, only_homoglyph_diff


def glyph_key(name):
    """A key that ignores spacing, case, and look-alike glyphs."""
    t = re.sub(r"[^A-Za-z0-9]", "", name).lower()
    out = []
    for ch in t:
        for cls in HOMOGLYPHS:
            low = cls.lower()
            if ch in low:
                ch = low[0]
                break
        out.append(ch)
    return "".join(out)


def gather(trees):
    """Every reading of every name, keyed so variants of one name group up."""
    votes = defaultdict(list)
    for t in trees:
        for row in t.get("rows", []):
            for field in ("name", "name_primary", "name_second"):
                val = (row.get(field) or "").strip()
                if val:
                    votes[glyph_key(row.get("name", val))].append(val)
    return votes


def decide(readings):
    counts = Counter(readings)
    if len(counts) == 1:
        return readings[0], "agreed", dict(counts)
    top, n = counts.most_common(1)[0]
    runners = [r for r, c in counts.items() if r != top]
    if all(only_homoglyph_diff(re.sub(r"[^A-Za-z0-9]", "", top),
                               re.sub(r"[^A-Za-z0-9]", "", r)) for r in runners):
        return top, "ambiguous-glyph", dict(counts)
    second = counts.most_common(2)[1][1] if len(counts) > 1 else 0
    if n > second:
        return top, "consensus", dict(counts)
    return top, "disputed", dict(counts)


def run(paths):
    trees = [json.load(open(p)) for p in paths]
    votes = gather(trees)
    out = {}
    for key, readings in votes.items():
        name, status, counts = decide(readings)
        out[key] = {"name": name, "status": status, "votes": counts}
    return out


def main():
    paths = [a for a in sys.argv[1:] if a.endswith(".json")]
    result = run(paths)
    settled = sum(1 for v in result.values() if v["status"] in ("agreed", "consensus"))
    print(f"{len(result)} distinct names across {len(paths)} frames; "
          f"{settled} settled, {len(result) - settled} still flagged\n")
    for v in sorted(result.values(), key=lambda v: v["name"]):
        if v["status"] == "agreed":
            continue
        print(f"  [{v['status']:15s}] {v['name']!r}")
        for reading, n in sorted(v["votes"].items(), key=lambda kv: -kv[1]):
            print(f"        {n} x {reading!r}")


if __name__ == "__main__":
    main()
