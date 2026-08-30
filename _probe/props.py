"""Where do the key/value splits actually land -- on a real properties panel,
and on the card that was mistaken for one."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, statistics
import note_reader


def look(png):
    bgr = cv2.imread(png)
    if bgr is None:
        print(f"{png}: nothing there"); return
    bgr = cv2.resize(bgr, (bgr.shape[1] * 3, bgr.shape[0] * 3),
                     interpolation=cv2.INTER_LANCZOS4)
    big = png.replace(".png", "_3x.png")
    cv2.imwrite(big, bgr)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mask = note_reader.ink_mask(gray)
    rows = note_reader.tess_rows(big, gray)
    for r in rows:
        r["xh"] = note_reader.row_x_height(mask, r)
    heights = [r["xh"] for r in rows if r["xh"] > 0]
    body = statistics.median(heights) if heights else 1.0
    rows = note_reader.note_body(rows, body)
    print(f"\n=== {os.path.basename(png)}  body_h={body:.1f} ===")
    for i, r in enumerate(rows[:12]):
        kv = note_reader.split_key_value(r, body)
        if not kv:
            continue
        words = r["words"]
        gaps = [(words[j + 1][1] - words[j][2], j) for j in range(len(words) - 1)]
        widest, at = max(gaps)
        print(f"  row{i:<2} key_x0={r['x0']:<6} val_x0={words[at+1][1]:<6} "
              f"gap={widest:<5} {kv[0]!r} -> {kv[1][:34]!r}")


for p in sys.argv[1:]:
    look(p)
