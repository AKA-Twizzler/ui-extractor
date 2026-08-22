"""The acceptance pass: one chronological note for every video.

    python acceptance.py [--redo] [--workers 3]

Walks the library longest-first with a few videos in flight at once, and
runs chronicle.py per video. Resumable by construction: a video whose note
already exists is skipped (unless --redo), so a machine restart mid-pass
costs only the videos it interrupted.

Why longest first, and why in parallel: one run uses about four of the
machine's twelve cores, so three runs fit side by side, and the wall clock
of the pass is then the longer of the longest video and a third of the
total -- the six-hour streams must start first or they finish last, alone.
Every line of the log carries the clock, and every finished video its read
time against its own length, so "slower than real time" is a number in the
log and not a feeling.
"""
import concurrent.futures
import glob
import os
import subprocess
import sys
import time

import machine

WORKERS = 3


def stamp():
    return time.strftime("%H:%M:%S")


def duration(video):
    """The video's length in seconds, from ffprobe; None when it cannot say."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "csv=p=0", video],
                           capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip())
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return None


def hm(secs):
    secs = int(secs)
    return f"{secs // 3600}h{(secs % 3600) // 60:02d}m" if secs >= 3600 else f"{secs // 60}m{secs % 60:02d}s"


def read_one(video):
    title = os.path.basename(os.path.dirname(video))
    t0 = time.time()
    r = subprocess.run(
        [sys.executable, "chronicle.py", video],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=os.path.dirname(os.path.abspath(__file__)))
    took = time.time() - t0
    length = duration(video)
    ratio = (took / length) if length else None
    tail = (r.stderr or r.stdout or "").strip().splitlines()
    return {"title": title, "ok": r.returncode == 0, "took": took,
            "length": length, "ratio": ratio,
            "tail": tail[-1][:160] if tail else "?"}


def main():
    workers = WORKERS
    if "--workers" in sys.argv:
        workers = max(1, int(sys.argv[sys.argv.index("--workers") + 1]))
    videos = []
    for folder in sorted(glob.glob(machine.here("/mnt/g/Video/*"))):
        found = sorted(glob.glob(os.path.join(folder, "*.mp4")))
        if found:
            videos.append((os.path.getsize(found[0]), found[0]))
    videos.sort(reverse=True)
    print(f"{stamp()}  {len(videos)} videos in the library, {workers} at a time",
          flush=True)
    todo = []
    skipped = 0
    for _, video in videos:
        title = os.path.basename(os.path.dirname(video))
        note = machine.here(f"/mnt/g/Images/{title}/{title}.md")
        if os.path.exists(note) and "--redo" not in sys.argv:
            skipped += 1
            print(f"{stamp()}  have  {title}", flush=True)
            continue
        todo.append(video)
    done = failed = 0
    slow = []
    t_start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for video in todo:
            title = os.path.basename(os.path.dirname(video))
            print(f"{stamp()}  read  {title} ...", flush=True)
            futures[pool.submit(read_one, video)] = title
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            speed = ""
            if res["ratio"] is not None:
                speed = (f" -- {hm(res['took'])} for a {hm(res['length'])} video, "
                         f"{res['ratio']:.2f}x real time")
                if res["ratio"] > 1.0:
                    slow.append((res["title"], res["ratio"]))
            if res["ok"]:
                done += 1
                print(f"{stamp()}  ok    {res['title']}{speed}", flush=True)
            else:
                failed += 1
                print(f"{stamp()}  FELL  {res['title']}{speed}: {res['tail']}",
                      flush=True)
    print(f"\n{stamp()}  {done} written, {skipped} already there, {failed} fell "
          f"over, {hm(time.time() - t_start)} for the pass", flush=True)
    if slow:
        print("slower than real time:", flush=True)
        for title, ratio in sorted(slow, key=lambda p: -p[1]):
            print(f"  {ratio:.2f}x  {title}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
