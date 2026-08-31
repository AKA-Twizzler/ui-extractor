#!/usr/bin/env python3
"""Take frames out of a video at named moments, as cleanly as the source allows.

Two things matter here and neither is obvious:

1. Frames are written as PNG, never JPEG. The source is already a compressed
   video; saving the grab as JPEG compresses it a second time, and the detail
   lost is exactly the fine text this job exists to read.

2. A moment is captured as a short BURST and the frames are median-stacked,
   not grabbed as a single frame. On a still screen every frame shows the same
   picture with different compression noise, so the median of the burst keeps
   what is really there and drops what the encoder invented. If the screen is
   moving, the burst is detected as moving and the single sharpest frame is
   used instead, because stacking motion would smear it.

3. A burst never crosses a cut. Video cuts between shots, and a burst centred
   on a moment can straddle one, so half its frames show a different scene
   entirely. The burst is split at any jump too large to be content changing,
   and only the shot containing the requested moment is kept. Without this the
   sharpest-frame rule can hand back a frame from the wrong shot, which is a
   silent and very convincing kind of wrong.

Run: python3 capture.py <video> <HH:MM:SS> [more timestamps...] --out DIR
"""
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np
import machine

BURST_SECONDS = 1.5
STILL_THRESHOLD = 1.5     # mean grey levels of frame-to-frame change
CUT_THRESHOLD = 12.0      # above this, the picture changed shot, not content


_SIZE = {}

def _frame_size(video):
    """The video's width and height, asked once per file."""
    if video not in _SIZE:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", video],
            capture_output=True, text=True, check=True).stdout.strip()
        w, h = (int(v) for v in out.split(",")[:2])
        _SIZE[video] = (w, h)
    return _SIZE[video]


def _ffmpeg_burst(video, timestamp, seconds):
    """The burst's frames themselves, decoded straight into memory.

    THE COST OF A FRAME WAS NEVER THE DECODING. Measured on one 1.5 s burst of
    a 4K AV1 file: decoding it and discarding the frames costs 1.18 s; decoding
    it and writing the forty-five PNGs this used to write costs 10.48 s, and
    every one of them is then read straight back by cv2.imread into the buffers
    ffmpeg already had. So ffmpeg hands the frames over directly now, and
    nothing is written. Proved lossless: the same burst both ways gives
    forty-five frames identical pixel for pixel (_probe/rawsame.py).

    ffmpeg's tmix filter is faster still (1.61 s) and may NOT be used --
    capture_moment needs every frame on its own, for the cut detection, the
    motion test, the sharpness pick and the stack, and tmix averages where this
    medians. The average is not the same instrument.

    """
    w, h = _frame_size(video)
    start = max(0.0, _to_seconds(timestamp) - seconds / 2)
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-i", video,
           "-t", f"{seconds:.3f}", "-vsync", "0",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    stride = w * h * 3
    # READ INTO THE FRAME, NOT INTO A GROWING BYTES OBJECT. subprocess.run's
    # capture_output collects a gigabyte by concatenation and then every frame
    # has to be copied out of it again; readinto fills each frame's own array
    # once and nothing is copied twice.
    out = []
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         bufsize=0)
    try:
        while True:
            frame = np.empty(stride, dtype=np.uint8)
            view = memoryview(frame)
            got = 0
            while got < stride:
                n = p.stdout.readinto(view[got:])
                if not n:
                    break
                got += n
            if got < stride:
                break                     # the tail of a truncated frame
            out.append(frame.reshape(h, w, 3))
    finally:
        p.stdout.close(); p.wait()
    return out


def _to_seconds(ts):
    parts = [float(p) for p in str(ts).split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def _slug(ts):
    s = _to_seconds(ts)
    return f"{int(s // 3600):02d}-{int(s % 3600 // 60):02d}-{int(s % 60):02d}"


MOVED_ON = 6           # how many bursts forward a damaged patch may be stepped over


BAND_ROWS = 256           # rows of the frame the median is taken over at once


def _median_stack(frames):
    """The per-pixel median of a burst, taken a band of rows at a time.

    The answer is the same to the byte; only the room it needs is different,
    and the room was the whole problem. Written as
    np.median(np.stack(frames).astype(np.float32), axis=0), a burst of 44
    frames at 3840x2160 costs

        the stack, as bytes                 1.1 GB
        cast to float32                     4.4 GB
        the median's own partition copy     4.4 GB
                                           -------
                                            9.9 GB at the peak

    which is what a sweep was measured holding, and what an earlier run died
    of with ONNX's 'bad allocation'. Nothing about a median of bytes needs
    floating point: partition keeps the frames' own dtype, and answering one
    band of rows at a time keeps the working set the size of the band instead
    of the size of the film. The same 44 frames now cost 260 MB.

    Bit-identical to what it replaces. For an odd count the middle value is
    the middle value either way; for an even count the old code averaged the
    two middle values as floats and truncated to uint8, and integer division
    of two non-negative bytes floors to the same number.
    """
    n = len(frames)
    mid = n // 2
    out = np.empty_like(frames[0])
    for y in range(0, frames[0].shape[0], BAND_ROWS):
        y1 = min(frames[0].shape[0], y + BAND_ROWS)
        band = np.stack([f[y:y1] for f in frames])
        if n % 2:
            out[y:y1] = np.partition(band, mid, axis=0)[mid]
        else:
            part = np.partition(band, [mid - 1, mid], axis=0)
            out[y:y1] = ((part[mid - 1].astype(np.uint16) + part[mid]) // 2
                         ).astype(np.uint8)
    return out


def capture_moment(video, timestamp, out_dir, seconds=BURST_SECONDS):
    """Return (path, how) for one moment: how is 'stacked' or 'sharpest'.

    A recording of this length is not always whole. The St. Jude replay is
    5.6GB and 6h20m, and at 00:45:00 its H264 stream is damaged: ffmpeg reports
    "Error splitting the input into NAL units", exits 0, and writes no frames
    at all. That is the file, not this program -- 2:12:59 of the same file
    reads perfectly -- but the run used to die on it, so one bad patch in a
    six-hour video returned nothing for the whole video.

    So a moment that cannot be decoded is stepped over, a burst at a time, and
    HOW FAR it moved is reported with the frame. A picture from a second later
    is worth having; a picture silently taken from somewhere else is not.
    """
    os.makedirs(out_dir, exist_ok=True)
    # A FRAME ALREADY CAPTURED IS NOT CAPTURED AGAIN.
    #
    # Capturing a moment costs twelve to fifteen seconds: a 1.5-second burst is
    # decoded, every frame of it measured for movement, and the median or the
    # sharpest taken. None of that is worth repeating for a frame already
    # sitting on disk, and a re-run of the same video used to pay all of it a
    # second time. `how` is kept in a sidecar beside the frame so a reused
    # capture reports exactly what the first one reported -- it goes into the
    # record, so a different wording would move the note.
    done = os.path.join(out_dir, f"{_slug(timestamp)}.png")
    how_file = done + ".how"
    if os.path.exists(done) and os.path.getsize(done) > 0 and os.path.exists(how_file):
        return done, open(how_file, encoding="utf-8").read().strip()
    moved, frames = 0.0, []
    for step in range(MOVED_ON):
        moved = step * seconds
        frames = _ffmpeg_burst(video, _to_seconds(timestamp) + moved, seconds)
        if frames:
            break
    if not frames:
        raise RuntimeError(
            f"no frames at {timestamp}, nor in the "
            f"{MOVED_ON * seconds:.0f}s after it; the file cannot be "
            "decoded here")
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    moves = [float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))
             for a, b in zip(grays, grays[1:])]

    # keep only the shot the requested moment belongs to
    target = len(frames) // 2
    lo, hi = 0, len(frames)
    for i, m in enumerate(moves):
        if m >= CUT_THRESHOLD:
            if i + 1 <= target:
                lo = i + 1
            else:
                hi = i + 1
                break
    cuts = sum(1 for m in moves if m >= CUT_THRESHOLD)
    frames, grays = frames[lo:hi], grays[lo:hi]
    moves = [float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))
             for a, b in zip(grays, grays[1:])]
    still = (max(moves) < STILL_THRESHOLD) if moves else True
    if still and len(frames) >= 3:
        out = _median_stack(frames)
        how = f"stacked {len(frames)} still frames"
    else:
        sharp = [cv2.Laplacian(g, cv2.CV_64F).var() for g in grays]
        out = frames[int(np.argmax(sharp))]
        how = f"sharpest of {len(frames)} moving frames"
    if cuts:
        how += f"; burst crossed {cuts} cut(s), kept the moment's own shot"
    if moved:
        how += (f"; moved {moved:.1f}s on, the file cannot be decoded at "
                f"{timestamp}")
    path = os.path.join(out_dir, f"{_slug(timestamp)}.png")
    cv2.imwrite(path, out, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    with open(path + ".how", "w", encoding="utf-8") as f:
        f.write(how)
    return path, how


def panes(png_path, min_height=0.75):
    """The vertical dividers the window draws, as x positions.

    A pane border is a column lit down almost the whole window, which is the
    one thing no text or icon ever is. The sidebar is the band between the
    first two.
    """
    img = cv2.imread(png_path, cv2.IMREAD_GRAYSCALE)
    bg = cv2.morphologyEx(img, cv2.MORPH_OPEN, np.ones((1, 41), np.uint8))
    diff = cv2.subtract(img, bg)
    cov = (diff > 4).mean(axis=0)
    return [x for x, v in enumerate(cov) if v >= min_height]


def main():
    args = [a for a in sys.argv[1:] if a != "--out"]
    out_dir = None
    if "--out" in sys.argv:
        out_dir = sys.argv[sys.argv.index("--out") + 1]
        args = [a for a in args if a != out_dir]
    video, stamps = args[0], args[1:]
    if out_dir is None:
        title = os.path.basename(os.path.dirname(video)) or "capture"
        out_dir = machine.here(f"/mnt/g/Images/{title}")
    for ts in stamps:
        path, how = capture_moment(video, ts, out_dir)
        print(f"{ts} -> {path}  ({how})")


if __name__ == "__main__":
    main()
