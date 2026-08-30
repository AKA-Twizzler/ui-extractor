import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sweep
sample = """--- 00:01:00  (stacked; interface on 90% of the frame) ---
  [pane 0: a terminal]
    aaa   <- the other engine read 'bbb'
    ccc   <- the other engine read 'ddd'
    eee   <- the other engine read 'fff'
    ggg
  [pane 1: text, not a tree]
    fine
--- 00:02:00  (stacked; interface on 80% of the frame) ---
    [this reader fell over and the run went on -- chat reader, pane 2: TypeError: x]
"""
for k, d in sweep.smells(sample):
    print(f"{k:<14} {d}")
