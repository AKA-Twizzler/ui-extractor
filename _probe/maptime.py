import sys, os, glob, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import spot, machine
title = sys.argv[1]
vid = sorted(glob.glob(f"G:/Video/{title}/*.mp4"))[0]
out = machine.here(f"/mnt/g/Images/{title}")
os.makedirs(out, exist_ok=True)
cache = os.path.join(out, "scan.json")
if os.path.exists(cache):
    os.unlink(cache)
import subprocess
d = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
     "-of","default=noprint_wrappers=1:nokey=1", vid],
     capture_output=True, text=True).stdout.strip())
t0 = time.perf_counter()
samples = spot.scan(vid, 10, cache)
took = time.perf_counter() - t0
runs = [r for r in spot.stretches(samples) if r["call"] == "screen"]
print(f"{title[:40]:42s} film {d/60:6.1f} min   mapping {took/60:6.1f} min   "
      f"ratio {took/d:5.2f}x   {len(samples)} samples, {len(runs)} screens")
