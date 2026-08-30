#!/usr/bin/env python3
"""Inside say_pane: which reader burns the 16-63s per pane.

Runs each cascade step separately, timed, on the panes fast1 already cut
(same frames, same crops). Also times the steps a claiming reader adds
(verify for trees, render is free) and the fallback tail (engine +
confirm_readings)."""
import glob
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")

import chat_reader
import columns
import console_reader
import note_reader
import tree_reader
import verify_names

WORK = r"G:\AI\Ethereal\ui-extractor\_probe\fast1_work"


def main():
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    panes = sorted(glob.glob(os.path.join(WORK, "00-0?-??_p?.png")))
    print(f"{len(panes)} panes\n")
    hdr = ("pane", "size", "tree", "console", "columns", "chat",
           "note", "engine", "confirm", "total")
    print(("{:<18}{:>12}" + "{:>9}" * 8).format(*hdr))
    for pp in panes:
        import cv2
        img = cv2.imread(pp)
        size = f"{img.shape[1]}x{img.shape[0]}"
        T = {}

        def tick(name, fn, *a, **k):
            t = time.perf_counter()
            try:
                r = fn(*a, **k)
            except Exception as why:
                r = {"err": f"{type(why).__name__}"}
            T[name] = time.perf_counter() - t
            return r

        tick("tree", tree_reader.read_tree, pp)
        tick("console", console_reader.read_console, pp)
        tick("columns", columns.read_list, pp)
        tick("chat", chat_reader.read_chat, pp, engine=engine)
        tick("note", note_reader.read_note, pp)
        got = tick("engine", engine, pp)
        res = got[0] if isinstance(got, tuple) else None
        texts = [t for _, t, _ in (res or [])]
        tick("confirm", verify_names.confirm_readings, pp, texts[:16])
        total = sum(T.values())
        name = os.path.basename(pp).replace(".png", "")
        print(("{:<18}{:>12}" + "{:>9.1f}" * 8).format(
            name, size, T["tree"], T["console"], T["columns"], T["chat"],
            T["note"], T["engine"], T["confirm"], total)
            + f"   {len(texts)} texts")
    print("\nfast2 done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
