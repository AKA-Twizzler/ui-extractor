"""Thin wrapper: the distinct windows of a frame live in shapes.windows."""
import sys, os, glob
sys.path.insert(0, "/home/trism/.claude/jobs/014c964f/tmp/replay")
import shapes
windows = shapes.windows
if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images"
    for f in sorted(glob.glob(os.path.join(d, "??-??-??.png"))):
        ws = windows(f)
        print("==", os.path.basename(f), len(ws))
        for r in sorted(ws, key=lambda r: r[0]):
            print("    l %5.1f  t %5.1f  r %5.1f  b %5.1f" %
                  (100*r[0]/3840, 100*r[1]/2160, 100*r[2]/3840, 100*r[3]/2160))
