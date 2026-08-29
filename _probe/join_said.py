"""Join the transcript's words into an existing records file the way the
pipeline does at read time: each moment its own words, its time to the
next moment's (transcript.words_at)."""
import io, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import machine, transcript
video = sys.argv[1]
title = transcript.title_of(video)
rec_path = os.path.join(machine.here(f"/mnt/g/Images/{title}"), "records.jsonl")
lines = [json.loads(l) for l in io.open(rec_path, encoding="utf-8")]
ms = [r for r in lines if "ts" in r]
ms.sort(key=lambda r: r.get("secs", 0))
saids = transcript.words_at(video, [r.get("secs", 0) for r in ms])
if saids is None:
    print("NO TRANSCRIPT"); sys.exit(1)
for r, sd in zip(ms, saids):
    r["said"] = sd
bak = rec_path + ".bak-nosaid"
if not os.path.exists(bak):
    os.replace(rec_path, bak)
with io.open(rec_path, "w", encoding="utf-8") as f:
    for r in lines:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("moments with words:", sum(1 for r in ms if r["said"]), "of", len(ms))
