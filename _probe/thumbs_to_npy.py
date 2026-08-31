"""Pull the skim's cached thumbnails out of a scan.json into one array.

scan.json keeps a 320x180 grey thumbnail for every sample -- which is why the
five-hour video's is 402 MB. Getting them into a numpy file once means every
alternative test for "has the screen changed" can be tried on the real
thumbnails in seconds, without decoding a frame.
"""
import json, io, sys
import numpy as np

src, out = sys.argv[1], sys.argv[2]
s = json.load(io.open(src, encoding="utf-8"))
samples = s["samples"]
th = np.array([sm["thumb"] for sm in samples], dtype=np.uint8)
ts = np.array([sm["t"] for sm in samples], dtype=np.int32)
call = np.array([1 if sm.get("call") == "screen" else 0 for sm in samples], dtype=np.uint8)
np.savez_compressed(out, thumb=th, t=ts, screen=call)
print("%d samples, thumbs %s -> %s" % (len(samples), th.shape, out))
