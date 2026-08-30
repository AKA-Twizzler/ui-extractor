"""Content-preservation comparison for the assembly round.

The assembled record changes indentation, label wording, and order
everywhere, so a word-for-word diff of the sweeps says nothing by itself.
What must hold is stronger and simpler: every CONTENT line of the old
report -- a reading, a mark, a table row -- still exists in the new one.
Labels and window headers are compared as counts, not text.

    python asmcmp.py <old_dir> <new_dir>
"""
import os
import sys
from collections import Counter


def content(path):
    """The report's readings, indent-free, labels dropped."""
    keep, labels = Counter(), Counter()
    for raw in open(path, encoding="utf-8", errors="replace"):
        s = raw.strip()
        if not s or s.startswith("=== ") or s.endswith("moments named"):
            continue
        if s.startswith("--- "):
            continue
        if s.startswith("["):
            # a label, unless it is one of the marks that carry readings
            for mark in ("[only one engine read these] ",
                         "[these sit over moving video] ",
                         "[said while this screen was up]"):
                if s.startswith(mark):
                    keep[s[len(mark):]] += 1
                    break
            else:
                head = s.split(":")[0].lstrip("[")
                labels[head.split(" -- ")[0].strip("]")] += 1
            continue
        keep[s] += 1
    return keep, labels


def main():
    old_dir, new_dir = sys.argv[1], sys.argv[2]
    names = sorted(os.listdir(old_dir))
    verdicts = []
    for name in names:
        if not name.endswith(".txt"):
            continue
        old_p = os.path.join(old_dir, name)
        new_p = os.path.join(new_dir, name)
        if not os.path.exists(new_p):
            verdicts.append((name, ["NEW REPORT MISSING"]))
            continue
        old_c, old_l = content(old_p)
        new_c, new_l = content(new_p)
        lost = old_c - new_c
        gained = new_c - old_c
        notes = []
        for line, n in lost.most_common():
            notes.append(f"lost x{n}: {line[:120]}")
        for line, n in gained.most_common():
            notes.append(f"gained x{n}: {line[:120]}")
        if old_l != new_l:
            for k in sorted(set(old_l) | set(new_l)):
                if old_l[k] != new_l[k]:
                    notes.append(f"labels '{k}': {old_l[k]} -> {new_l[k]}")
        verdicts.append((name, notes))
    clean = sum(1 for _, n in verdicts if not n)
    print(f"{clean} of {len(verdicts)} reports carry identical content\n")
    for name, notes in verdicts:
        if not notes:
            continue
        print(f"== {name}")
        for note in notes[:40]:
            print("   " + note)
        if len(notes) > 40:
            print(f"   ... and {len(notes) - 40} more lines")
        print()


if __name__ == "__main__":
    main()
