#!/usr/bin/env python3
"""Turn a records file back into the record it was written from.

    python3 render.py <records.jsonl>            the diary, exactly as printed

A records file keeps every character the run printed, moment by moment,
beside the measurements those lines came from. This is the first and
simplest rendering of it: the diary itself, byte for byte. The check
suite holds this rendering identical to the run's own output, which is
the proof that the records carry everything the record says. The drawn
note shape is a second rendering of the same file and lives in draw.py.
"""
import json
import sys


def entries(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def diary(path):
    return "".join(e.get("text", "") for e in entries(path))


def main():
    sys.stdout.write(diary(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
