import sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, capture

def peak_gb():
    r = subprocess.run(["wmic", "process", "where", f"processid={os.getpid()}",
                        "get", "PeakWorkingSetSize"],
                       capture_output=True, text=True)
    for line in r.stdout.split():
        if line.isdigit():
            return int(line) * 1024 / 1e9      # wmic reports kilobytes
    return -1.0

which = sys.argv[1]
frames = [np.full((2160, 3840, 3), i % 256, np.uint8) for i in range(44)]
print(f"44 frames of 3840x2160 held; peak so far {peak_gb():.2f} GB")
if which == "new":
    out = capture._median_stack(frames)
else:
    out = np.median(np.stack(frames).astype(np.float32), axis=0).astype(np.uint8)
print(f"{which:>4} median done, shape {out.shape}; PEAK {peak_gb():.2f} GB")
