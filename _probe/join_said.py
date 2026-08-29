"""Join the transcript's words into an existing records file, the way the
pipeline does at read time: the video map from the cached scan, every
stretch given its words, every moment given its stretch's words."""
import io, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import machine, spot, transcript
video = sys.argv[1]
title = transcript.title_of(video)
out_dir = machine.here(f"/mnt/g/Images/{title}")
rec_path = os.path.join(out_dir, "records.jsonl")
samples = spot.scan(video, 10, os.path.join(out_dir, "scan.json"))
runs = spot.stretches(samples)
if transcript.words_for(video, runs) is None:
    print("NO TRANSCRIPT"); sys.exit(1)
def said_at(secs):
    best = None
    for r in runs:
        if r["start"] <= secs:
            best = r
    return (best or {}).get("said")
lines = [json.loads(l) for l in io.open(rec_path, encoding="utf-8")]
n = 0
for r in lines:
    if "ts" in r:
        s = said_at(r.get("secs", 0))
        r["said"] = s
        n += 1 if s else 0
bak = rec_path + ".bak-nosaid"
if not os.path.exists(bak):
    os.replace(rec_path, bak)
with io.open(rec_path, "w", encoding="utf-8") as f:
    for r in lines:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("moments with words:", n, "of", sum(1 for r in lines if "ts" in r))
