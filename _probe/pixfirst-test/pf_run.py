"""Read the three test panes and print each as one JSON line (rows with cells, cut, conf)."""
import sys, json, os, time
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor\_probe"); sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import pixfirst
F = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\%s.png"
truth = json.load(open(r"G:\AI\Ethereal\ui-extractor\_probe\pixfirst-test\truth.json"))
for pane in truth["panes"]:
    t0 = time.time()
    rec = pixfirst.read_frame(F % pane["frame"], None, "", wb=pane["wb"], list_box=True)
    print(json.dumps({"frame": pane["frame"], "wb": pane["wb"], "secs": round(time.time() - t0, 1), "up": rec["up"],
                      "rows": [{"cells": r["cells"], "cut": r["cut"], "conf": r["conf"]} for r in rec["rows"]]}))
