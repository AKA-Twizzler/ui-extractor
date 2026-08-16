#!/usr/bin/env python3
"""Grade a tree read against the ground-truth fixture.

The fixture is Tristan's own reading of the 00:02:09 sidebar and is the
definition of done. This prints the verdict as counts, so a run's quality is
a number rather than an impression, and names every row it got wrong.

Run: python3 score.py <tree.json>
     python3 score.py <sidebar.png>     (reads the frame first)
"""
import json
import re
import sys

import fixture
import machine


def key(s):
    """Alignment key: OCR loses spaces and punctuation, never letters."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def tidy(s):
    """Name comparison: forgive spacing, hold every character to account."""
    return re.sub(r"\s+", " ", s).strip()


def load_rows(path):
    if path.endswith(".json"):
        return json.load(open(path))["rows"]
    import tree_reader
    return tree_reader.read_tree(path)["rows"]


def grade(rows, fx):
    if not fx:
        return None
    start = None
    first = key(fx[0]["name"])
    for i, r in enumerate(rows):
        if key(r["name"]) == first:
            start = i
            break
    if start is None:
        return {"aligned": False}

    got = rows[start:start + len(fx)]
    res = {"aligned": True, "fixture_rows": len(fx), "read_rows": len(got),
           "name_exact": 0, "name_loose": 0, "kind": 0, "depth": 0,
           "chevron": 0, "all_four": 0, "misses": []}
    for i, f in enumerate(fx):
        if i >= len(got):
            res["misses"].append((f["name"], "row missing from the read"))
            continue
        g = got[i]
        name_exact = tidy(g["name"]) == tidy(f["name"])
        name_loose = key(g["name"]) == key(f["name"])
        kind_ok = g["kind"] == f["kind"]
        depth_ok = g["depth"] == f["depth"]
        chev_ok = (g["chevron"] or None) == (f["chevron"] or None)
        res["name_exact"] += name_exact
        res["name_loose"] += name_loose
        res["kind"] += kind_ok
        res["depth"] += depth_ok
        res["chevron"] += chev_ok
        res["all_four"] += (name_exact and kind_ok and depth_ok and chev_ok)
        if not (name_exact and kind_ok and depth_ok and chev_ok):
            why = []
            if not name_exact:
                why.append(f"name {g['name']!r} != {f['name']!r}")
            if not kind_ok:
                why.append(f"kind {g['kind']} != {f['kind']}")
            if not depth_ok:
                why.append(f"depth {g['depth']} != {f['depth']}")
            if not chev_ok:
                why.append(f"chevron {g['chevron']} != {f['chevron']}")
            res["misses"].append((f["name"], "; ".join(why)))
    return res


def main():
    rows = load_rows(sys.argv[1])
    fx = fixture.load()
    r = grade(rows, fx)
    if not r or not r.get("aligned"):
        print("FAIL: could not align the read against the fixture")
        sys.exit(1)
    n = r["fixture_rows"]
    print(f"against the fixture, {n} rows:")
    print(f"  names, exact        {r['name_exact']:>3}/{n}")
    print(f"  names, ignoring spacing {r['name_loose']:>3}/{n}")
    print(f"  folder vs file      {r['kind']:>3}/{n}")
    print(f"  depth               {r['depth']:>3}/{n}")
    print(f"  open vs closed      {r['chevron']:>3}/{n}")
    print(f"  ALL FOUR correct    {r['all_four']:>3}/{n}")
    if r["misses"]:
        print("\n  rows not fully correct:")
        for name, why in r["misses"]:
            print(f"    {name:36s} {why}")
    sys.exit(0 if r["all_four"] == n else 1)


if __name__ == "__main__":
    main()
