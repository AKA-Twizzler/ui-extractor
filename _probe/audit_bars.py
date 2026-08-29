import re, sys, os
from PIL import Image, ImageDraw
note, out, frames = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
t = open(note, encoding="utf-8").read()
crops = []
def pct(style, k):
    m = re.search(k + r':(-?[\d.]+)%', style); return float(m.group(1)) if m else None
for m in re.finditer(r'<div class="sn-stage">(.*?)<div class="sn-stamp">(.*?)</div></div></div>', t, re.S):
    body, stamp = m.group(1), m.group(2); ts = stamp[:8]
    zm = re.search(r'class="sn-zoom" style="([^"]*)"', body)
    zoom = [pct(zm.group(1), k) for k in ("left", "top", "width", "height")] if zm else None
    parts = re.split(r'(?=<div class="sn-slot" style=)', body)
    for i, part in enumerate(p for p in parts if p.startswith('<div class="sn-slot"')):
        style = re.match(r'<div class="sn-slot" style="([^"]*)"', part).group(1)
        box = [pct(style, k) for k in ("left", "top", "width", "height")]
        clip = re.search(r'clip-path:inset\(([^)]*)\)', style)
        thumbs = []
        for tm in re.finditer(r'<div class="sn-thumb" style="([^"]*)"', part):
            before = part[:tm.start()]
            panes = re.findall(r'class="(sn-side|sn-body|sn-tree|sn-doc)', before)
            thumbs.append("%s %s" % (panes[-1] if panes else "?", tm.group(1)))
        crops.append((ts, i, box, clip.group(1) if clip else "", zoom, thumbs))
W, H = 3840, 2160
CW, CH = 940, 540
sheets = [crops[i:i+4] for i in range(0, len(crops), 4)]
for n, group in enumerate(sheets):
    sheet = Image.new("RGB", (2 * CW + 30, 2 * (CH + 70) + 30), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for j, (ts, i, box, clip, zoom, thumbs) in enumerate(group):
        fr = Image.open(os.path.join(frames, ts.replace(":", "-") + ".png")).convert("RGB")
        l, tp, w, h = box
        if zoom:
            zl, zt, zw, zh = zoom
            x0 = (l - zl) / zw * W; y0 = (tp - zt) / zh * H; x1 = (l + w - zl) / zw * W; y1 = (tp + h - zt) / zh * H
        else:
            x0 = l / 100 * W; y0 = tp / 100 * H; x1 = (l + w) / 100 * W; y1 = (tp + h) / 100 * H
        x0, y0 = max(0, int(x0)), max(0, int(y0)); x1, y1 = min(W, int(x1)), min(H, int(y1))
        if x1 - x0 < 10 or y1 - y0 < 10: continue
        c = fr.crop((x0, y0, x1, y1)); s = min(CW / c.width, CH / c.height); c = c.resize((max(1, int(c.width * s)), max(1, int(c.height * s))))
        ox = 10 + (j % 2) * (CW + 10); oy = 10 + (j // 2) * (CH + 70)
        sheet.paste(c, (ox, oy))
        d.text((ox, oy + CH + 4), "%s slot %d %s%s" % (ts, i, "zoomed " if zoom else "", ("clip " + clip) if clip else ""), fill=(255, 220, 80))
        d.text((ox, oy + CH + 18), "note thumbs: " + ("; ".join(thumbs) if thumbs else "NONE"), fill=(120, 220, 255))
        d.text((ox, oy + CH + 32), "crop px %d,%d-%d,%d scale %.2f" % (x0, y0, x1, y1, s), fill=(160, 160, 160))
    sheet.save(os.path.join(out, "sheet-%02d.png" % n))
print(len(crops), "crops in", len(sheets), "sheets")
