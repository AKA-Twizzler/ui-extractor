import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import glob, overlay
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
title = "How To Generate Leads With AI"
vid = sorted(glob.glob(f"G:/Video/{title}/*.mp4"))[0]
work = f"G:/Images/{title}/_looks"
for secs in (181, 363):
    looks = overlay.frames_across(vid, secs, workdir=work)
    got = [g["text"] for g in overlay.standing_text(looks, engine=eng)]
    print(f"{secs}s ({secs//60:02d}:{secs%60:02d})  admitted: {got}")
