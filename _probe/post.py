import sys, cv2
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import checks, panes, tree_reader
img = cv2.imread(checks.frame("post", "00:00:30"))
print("windows:", panes._measured_windows(img))
regs = checks.regions("post", "00:00:30")
print("panes:", len(regs))
for r in regs:
    rows = tree_reader.ocr_rows(r)
    has_blue = any("Plan-2026" in x["text"] for x in rows)
    has_plain = any(x["text"].strip().lower().startswith("daily") for x in rows)
    print("   %-22s rows %3d  Plan-2026 %s  daily %s"
          % (r.split("\\")[-1], len(rows), has_blue, has_plain))
