import sys, os, glob, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import spot
for c in sorted(glob.glob("G:/Images/*/scan.json")):
    title = os.path.basename(os.path.dirname(c))
    try:
        samples = json.load(open(c))
    except Exception as why:
        print(f"  {title[:40]:42s} unreadable: {why}"); continue
    if isinstance(samples, dict):
        samples = samples.get("samples", samples.get("rows", []))
    try:
        runs = [r for r in spot.stretches(samples) if r["call"] == "screen"]
    except Exception as why:
        print(f"  {title[:40]:42s} {len(samples)} samples, stretches failed: {why}")
        continue
    print(f"  {title[:40]:42s} {len(samples):5d} samples -> {len(runs):4d} distinct screens")
