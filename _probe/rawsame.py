"""Are the frames from a raw pipe the same pixels as the frames from PNGs?"""
import subprocess, tempfile, os, sys, glob
import numpy as np, cv2
V = sys.argv[1]; T = float(sys.argv[2]); SEC = 1.5
start = max(0.0, T - SEC/2)
out = subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries",
                      "stream=width,height","-of","csv=p=0", V], capture_output=True, text=True).stdout.strip()
w, h = (int(v) for v in out.split(",")[:2])
print("video is %d x %d" % (w, h))
with tempfile.TemporaryDirectory() as work:
    subprocess.run(["ffmpeg","-y","-v","error","-ss",f"{start:.3f}","-i",V,"-t",f"{SEC:.3f}",
                    "-vsync","0", os.path.join(work,"f_%04d.png")], check=True, capture_output=True)
    files = sorted(glob.glob(os.path.join(work,"f_*.png")))
    png = [cv2.imread(f, cv2.IMREAD_COLOR) for f in files]
got = subprocess.run(["ffmpeg","-y","-v","error","-ss",f"{start:.3f}","-i",V,"-t",f"{SEC:.3f}",
                      "-vsync","0","-f","rawvideo","-pix_fmt","bgr24","-"], capture_output=True).stdout
stride = w*h*3; n = len(got)//stride
raw = list(np.frombuffer(got[:n*stride], dtype=np.uint8).reshape(n,h,w,3))
print("PNG path %d frames, raw pipe %d frames" % (len(png), len(raw)))
same = sum(1 for a,b in zip(png,raw) if a.shape==b.shape and np.array_equal(a,b))
print("frames identical pixel for pixel: %d of %d" % (same, min(len(png),len(raw))))
if same < min(len(png),len(raw)):
    for i,(a,b) in enumerate(zip(png,raw)):
        if not np.array_equal(a,b):
            print("   frame %d differs, biggest gap %d" % (i, int(np.abs(a.astype(int)-b.astype(int)).max()))); break
