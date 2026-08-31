# STAGED, NOT APPLIED. The replacement for capture.py's _ffmpeg_burst and the
# imread loop that follows it. Apply only when no run is in flight -- the
# running pipeline holds capture.py loaded.
#
# WHY, MEASURED on one 1.5 s burst of the 4K AV1 file (44 frames):
#     ffmpeg decode only, frames discarded          1.18 s   <- the floor
#     ffmpeg decode + raw frames down a pipe        2.18 s
#     ffmpeg decode + writing 44 PNGs (what we do) 10.48 s   + reading all 44 back
# The decoding is a second. The rest is turning arrays into PNGs and straight
# back into arrays -- ffmpeg encodes forty-four 4K pictures and cv2.imread
# decodes the same forty-four into the buffers ffmpeg already had.
#
# ffmpeg's tmix filter is faster still (1.61 s) and cannot be used: capture_moment
# needs every frame on its own -- for the cut detection, the motion test, the
# sharpness pick and the median stack -- and tmix averages where this medians.

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


def _ffmpeg_burst(video, timestamp, seconds, workdir=None):
    """The burst's frames themselves, decoded straight into memory.

    `workdir` is accepted and ignored: nothing is written any more. The frames
    come back as the same BGR arrays cv2.imread was handing over, so everything
    downstream is untouched.
    """
    w, h = _frame_size(video)
    start = max(0.0, _to_seconds(timestamp) - seconds / 2)
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-i", video,
           "-t", f"{seconds:.3f}", "-vsync", "0",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    got = subprocess.run(cmd, capture_output=True)
    buf = got.stdout or b""
    stride = w * h * 3
    n = len(buf) // stride
    if n == 0:
        return []
    # the tail of a truncated frame is dropped rather than reshaped into noise
    return list(np.frombuffer(buf[:n * stride], dtype=np.uint8).reshape(n, h, w, 3))


# --- and in capture_moment, the burst loop becomes ---
#
#     frames = []
#     for step in range(MOVED_ON):
#         moved = step * seconds
#         frames = _ffmpeg_burst(video, _to_seconds(timestamp) + moved, seconds)
#         if frames:
#             break
#     if not frames:
#         raise RuntimeError(...)          # unchanged wording
#     grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
#
# The `with tempfile.TemporaryDirectory() as work:` wrapper goes, along with the
# `for stale in os.listdir(work)` cleanup and the `frames = [cv2.imread(f) ...]`
# and `frames = [f for f in frames if f is not None]` lines -- a frame that did
# not decode never reaches the list now.
#
# One thing to keep: np.frombuffer gives a READ-ONLY view. Nothing downstream
# writes into a frame today, but _median_stack or a later change might, so if
# anything raises "assignment destination is read-only", .copy() the frames.
