#!/usr/bin/env python3
"""The last gate: every drawn picture rendered and laid beside its real frame.

    python3 compare.py <note.md> <frames-dir> [<out-dir>] [--floor 0.55]

The note is what Obsidian shows; the frame is what the screen showed. This
turns the note's HTML into pixels the way Obsidian would (the vault's own
screen-notes.css, headless Edge on the Windows side), puts each desktop
picture under the frame it claims, and writes every window card on its own.
Then it measures the two the one way that cannot grade its own homework:
against the frame's pixels, never the reader's rectangles.

The measure is ink agreement. Both images are reduced to where an eye sees
ink -- text and edges -- on a coarse grid. `real` is the share of the
drawing's ink that lands where the frame has ink (nothing invented, nothing
misplaced); `covered` is the share of the frame's ink the drawing puts down
(nothing missing). The camera's box is left out of both, since the rule is
to outline it and never draw it. A number is a pointer, not a verdict: the
side-by-side is the gate, and a picture is finished when a person reading
both sees no difference. The number exists so a change can be told from
noise, and so a picture that got worse says so before anyone opens it.

Why Edge: Brave is Tristan's open browser and its profile is locked, so a
headless Brave hangs for ever. Edge is on every Windows machine and idle.
Why a browser at all: the pictures use container units and aspect-ratio,
which wkhtmltoimage's WebKit cannot draw, so a render from it would be a
picture of the wrong thing.

Output: <out-dir>/cmp/pic-HH-MM-SS.png (frame over drawing),
<out-dir>/png/*.png (every picture and card alone), a table on stdout, and
exit 1 when any picture scores under the floor, so a build can gate on it.
"""
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageChops, ImageFilter

# No cv2 on purpose: the reader runs on the Windows Python, which has it,
# but this gate drives Edge by its WSL path and runs on the WSL Python,
# which does not. PIL and numpy carry everything it needs.

EDGE = "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
CSS_PATH = "/mnt/nas/obsidian-vault/.obsidian/snippets/screen-notes.css"
VARS = (":root{--background-primary:#1e1e1e;--background-primary-alt:#262626;--background-secondary:#222;"
        "--background-modifier-border:#3a3a3a;--text-muted:#9a9a9a;--text-normal:#dcddde;--interactive-accent:#7f6df2;}"
        "body{background:#1e1e1e;color:#dcddde;font-family:Inter,'Segoe UI',sans-serif;font-size:16px;margin:0;padding:0;}"
        ".cell{overflow:hidden;box-sizing:border-box;padding:20px;}")
BG = (30, 30, 30)
PIC_W, PIC_H = 960, 540          # the picture's own size: the drawing works in these pixels
PIC_CELL = 600                   # one picture per cell of this height on the batch page
CARD_CELL = 2100                 # one card per cell; the tallest card seen is 1826
CELL_GRID = 10                   # ink is judged on 10x10-pixel cells of the 960x540 picture


def win_path(p):
    """/mnt/g/x -> G:\\x, for the browser on the Windows side."""
    m = re.match(r"^/mnt/([a-z])/(.*)$", p)
    if not m:
        raise SystemExit("compare.py: the out-dir must sit on a Windows drive (/mnt/<letter>/...), got " + p)
    return m.group(1).upper() + ":\\" + m.group(2).replace("/", "\\")


def edge_profile(name):
    """Edge's scratch profile, on the FAST local disk -- never beside the output.

    It used to live in the out-dir, which sits on G:, a USB drive that also
    carries the images, the WSL disk and whatever else is being copied at the
    time. Edge writes its profile as it starts, so the render inherited that
    drive's contention: measured on one and the same page, 2 seconds with the
    profile on C: against 179 seconds with it on G:, and past the 300-second
    limit altogether when the drive was busy, which failed the whole compare.
    The pictures are unaffected -- only where the browser keeps its scratch.
    """
    base = "/mnt/c/Users/%s/AppData/Local/Temp/ui-extractor-edge" % os.environ.get("WINUSER", "trism")
    d = os.path.join(base, name)
    os.makedirs(d, exist_ok=True)
    return d


def file_url(p):
    m = re.match(r"^/mnt/([a-z])/(.*)$", p)
    return "file:///%s:/%s" % (m.group(1).upper(), m.group(2))


def parts_of(note_path):
    """Every desktop picture and every window card in the note, with the
    heading each stands under."""
    heading = ""
    pics, cards = [], []
    for i, l in enumerate(open(note_path, encoding="utf-8").read().split("\n"), start=1):
        if l.startswith("## ") or l.startswith("### ") or l.startswith("#### "):
            heading = l.lstrip("# ").strip()
        if l.startswith('<div class="sn-stage">'):
            pics.append((i, heading, l))
        elif l.startswith('<div class="sn-window'):
            cards.append((i, heading, l))
    return pics, cards


def stamp_of(heading):
    return heading.split(" - ")[0].split(" to ")[0].strip()


def render_page(out, name, cells, cell_h, css, scale=1):
    """One page, one item per fixed-height cell, one browser launch. At
    `scale` 2 the page is laid out twice as wide and tall, so a picture
    of the whole desktop still has the pixels to be judged on the part
    of it the video zoomed in on."""
    html_dir = os.path.join(out, "html")
    os.makedirs(html_dir, exist_ok=True)
    cell_h = cell_h * scale
    body = "".join("<div class='cell' style='height:%dpx'><div class='markdown-preview-view screen-note' "
                   "style='width:%dpx'><div class='markdown-preview-sizer'>%s</div></div></div>" % (cell_h, 960 * scale, c)
                   for c in cells)
    page = ("<!doctype html><html><head><meta charset='utf-8'><style>" + VARS + css + "</style></head><body>"
            + body + "</body></html>")
    hp = os.path.join(html_dir, name + ".html")
    open(hp, "w", encoding="utf-8").write(page)
    png = os.path.join(html_dir, name + ".png")
    if os.path.exists(png):
        os.remove(png)
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                    "--user-data-dir=" + win_path(edge_profile(name)),
                    "--window-size=%d,%d" % (1000 * scale, cell_h * len(cells)),
                    "--screenshot=" + win_path(png), file_url(hp)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    if not os.path.exists(png):
        raise SystemExit("compare.py: Edge wrote no screenshot for " + hp)
    im = Image.open(png).convert("RGB")
    if im.height < cell_h * len(cells):
        raise SystemExit("compare.py: the page came back %d tall for %d cells of %d; render fewer per page"
                         % (im.height, len(cells), cell_h))
    return [im.crop((0, k * cell_h, im.width, (k + 1) * cell_h)) for k in range(len(cells))]


def trim(im):
    box = ImageChops.difference(im, Image.new("RGB", im.size, BG)).getbbox()
    return im.crop(box) if box else im


def ink_grid(im):
    """Where an eye sees ink: local contrast, on a coarse grid."""
    small = im.convert("L").resize((PIC_W, PIC_H))
    g = np.asarray(small, dtype=np.float32)
    blur = np.asarray(small.filter(ImageFilter.GaussianBlur(3)), dtype=np.float32)
    m = (np.abs(g - blur) > 16).astype(np.float32)
    cells = m.reshape(PIC_H // CELL_GRID, CELL_GRID, PIC_W // CELL_GRID, CELL_GRID).mean(axis=(1, 3))
    return cells > 0.03


def zoom_box(stage_html):
    """Where the video zoomed in, as the picture says it (left, top, right,
    bottom in 0..1 of the picture), or None when the frame was the whole
    screen. The picture is always the whole desktop; a zoomed frame is a
    crop of it, so the comparison is made on that crop of the drawing."""
    m = re.search(r'class="sn-zoom" style="([^"]*)"', stage_html)
    if not m:
        return None
    st = dict(re.findall(r"(left|top|width|height):(-?[\d.]+)%", m.group(1)))
    if len(st) != 4:
        return None
    l, t, w, h = (float(st[k]) / 100 for k in ("left", "top", "width", "height"))
    return (l, t, l + w, t + h) if w > 0.05 and h > 0.05 else None


def region_mask(stage_html, class_pat, zb=None):
    """Cells covered by the boxes whose class matches `class_pat`, read from
    their left/top/width/height percentages -- carried into the zoomed
    crop's own space when the picture holds one."""
    mask = np.zeros((PIC_H // CELL_GRID, PIC_W // CELL_GRID), dtype=bool)
    for m in re.finditer(r'class="' + class_pat + r'" style="([^"]*)"', stage_html):
        st = dict(re.findall(r"(left|top|width|height):(-?[\d.]+)%", m.group(1)))
        if len(st) == 4:
            l, t, w, h = (float(st[k]) for k in ("left", "top", "width", "height"))
            if zb:
                zw, zh = zb[2] - zb[0], zb[3] - zb[1]
                l, t = (l / 100 - zb[0]) / zw * 100, (t / 100 - zb[1]) / zh * 100
                w, h = w / zw, h / zh
            y0, y1 = int(t / 100 * mask.shape[0]), int(np.ceil((t + h) / 100 * mask.shape[0]))
            x0, x1 = int(l / 100 * mask.shape[1]), int(np.ceil((l + w) / 100 * mask.shape[1]))
            mask[max(0, y0):y1, max(0, x0):x1] = True
    return mask


def camera_mask(stage_html, zb=None):
    """Cells under the camera's box, which the drawing outlines and never draws."""
    return region_mask(stage_html, r'sn-camera[^"]*', zb)


def behind_only_mask(stage_html, zb=None):
    """Cells that are BEHIND-ONLY: covered by an outline (a window drawn
    behind) and by no filled window on top. Tristan's rule is that only the
    top layer gets full content and everything behind is an outline, so the
    frame's ink in a behind-only region is content the drawing is SUPPOSED
    to omit -- it must not count against coverage, any more than the camera
    does. A behind window that a front window is drawn over is not excluded:
    that ground is the front window's, and its content is scored normally."""
    outline = region_mask(stage_html, r'sn-ghost(?: sn-\w+)*', zb)
    filled = region_mask(stage_html, r'sn-slot(?: sn-\w+)*', zb)
    return outline & ~filled


def blobs(grid, top=3):
    """The largest patches of a boolean grid, as percent boxes of the screen.
    Patches are found by a plain flood fill over the coarse grid, which is
    54 by 96 cells and needs no library for it."""
    seen = np.zeros(grid.shape, dtype=bool)
    out = []
    H, W = grid.shape
    for y0 in range(H):
        for x0 in range(W):
            if not grid[y0, x0] or seen[y0, x0]:
                continue
            stack, cells = [(y0, x0)], []
            seen[y0, x0] = True
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < H and 0 <= nx < W and grid[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            out.append((len(cells), "%.0f-%.0f%% across, %.0f-%.0f%% down" % (
                100.0 * min(xs) / W, 100.0 * (max(xs) + 1) / W,
                100.0 * min(ys) / H, 100.0 * (max(ys) + 1) / H)))
    out.sort(reverse=True)
    return [b for _, b in out[:top]]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    floor = 0.0
    if "--floor" in sys.argv:
        floor = float(sys.argv[sys.argv.index("--floor") + 1])
        args = [a for a in args if a != sys.argv[sys.argv.index("--floor") + 1]]
    if len(args) < 2:
        raise SystemExit(__doc__)
    note, frames = args[0], args[1]
    out = os.path.abspath(args[2] if len(args) > 2
                          else os.path.join(os.path.dirname(os.path.abspath(__file__)), "_compare"))
    css = open(CSS_PATH, encoding="utf-8").read()
    for d in ("cmp", "png"):
        os.makedirs(os.path.join(out, d), exist_ok=True)

    pics, cards = parts_of(note)
    rows, worst = [], 1.0
    shots = []
    for start in range(0, len(pics), 6):
        shots += render_page(out, "pictures-%d" % (start // 6), [p[2] for p in pics[start:start + 6]], PIC_CELL, css, scale=2)
    if pics:
        for (line, heading, stage), shot in zip(pics, shots):
            stamp = stamp_of(heading)
            name = "pic-" + stamp.replace(":", "-")
            drawn = trim(shot)
            drawn.save(os.path.join(out, "png", name + ".png"))
            frame_path = os.path.join(frames, stamp.replace(":", "-") + ".png")
            if not os.path.exists(frame_path):
                rows.append((name, line, None, None, "no frame at " + frame_path))
                continue
            frame = Image.open(frame_path).convert("RGB").resize((PIC_W, PIC_H))
            # a zoomed frame is compared with the same crop of the drawing
            zb = zoom_box(stage)
            if zb:
                dw, dh = drawn.size
                drawn = drawn.crop((int(zb[0] * dw), int(zb[1] * dh), int(zb[2] * dw), int(zb[3] * dh)))
            # `real` (is the drawn ink right?) is judged everywhere but under
            # the camera. `covered` (did the drawing put down the frame's
            # ink?) is judged only where the drawing is SUPPOSED to carry
            # content -- not under the camera, and not in a behind-only region
            # the rule says to leave an outline. Otherwise the correct
            # picture, which omits behind content by design, scores as if it
            # had lost it.
            keep_real = ~camera_mask(stage, zb)
            keep_cov = keep_real & ~behind_only_mask(stage, zb)
            Dg = ink_grid(drawn)
            Fg = ink_grid(frame)
            D = Dg & keep_real
            F = Fg & keep_real
            real = (D & F).sum() / max(1, D.sum())
            Dc, Fc = Dg & keep_cov, Fg & keep_cov
            covered = (Dc & Fc).sum() / max(1, Fc.sum())
            worst = min(worst, real, covered)
            invented = blobs(D & ~F)
            missing = blobs(Fc & ~Dc)
            rows.append((name, line, real, covered, "invented: %s | missing: %s" % ("; ".join(invented) or "-", "; ".join(missing) or "-")))
            cmp = Image.new("RGB", (PIC_W, PIC_H * 2 + 10), BG)
            cmp.paste(frame, (0, 0))
            cmp.paste(drawn.resize((PIC_W, PIC_H)) if drawn.size != (PIC_W, PIC_H) else drawn, (0, PIC_H + 10))
            cmp.save(os.path.join(out, "cmp", name + ".png"))

    k = 0
    for start in range(0, len(cards), 4):
        batch = cards[start:start + 4]
        shots = render_page(out, "cards-%d" % (start // 4), [c[2] for c in batch], CARD_CELL, css)
        for (line, heading, _), shot in zip(batch, shots):
            k += 1
            im = trim(shot)
            im.save(os.path.join(out, "png", "card-%02d.png" % k))
            rows.append(("card-%02d" % k, line, None, None, "%dx%d  %s" % (im.width, im.height, heading[:60])))

    print("%-14s %5s %6s %8s  %s" % ("picture", "line", "real", "covered", "where the ink disagrees (screen percent)"))
    for name, line, real, covered, detail in rows:
        if real is None:
            print("%-14s %5d %6s %8s  %s" % (name, line, "-", "-", detail))
        else:
            print("%-14s %5d %6.2f %8.2f  %s" % (name, line, real, covered, detail))
    print("side by side: %s   alone: %s" % (os.path.join(out, "cmp"), os.path.join(out, "png")))
    if floor and worst < floor:
        print("FAIL: a picture scored %.2f, under the floor of %.2f" % (worst, floor))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
