"""Score the screenness test against the 120 labelled frames.

'uncertain' is not a wrong answer -- it hands the frame to the slow OCR test,
which is right but costly -- so it is counted separately from a wrong call.
"""
import json, os, sys, glob
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import screenness as sc

TRUTH = json.load(open("_probe/screen_truth.json"))


def score(call, show_wrong=False):
    tot = {"right": 0, "wrong": 0, "unsure": 0}
    per = {}
    for d, fs in sorted(TRUTH.items()):
        n = {"right": 0, "wrong": 0, "unsure": 0}
        for f, want in sorted(fs.items()):
            path = os.path.join("_probe/scratch/set", d, f)
            got = call(cv2.imread(path))
            k = ("unsure" if got == "uncertain" else
                 "right" if got == want else "wrong")
            n[k] += 1
            if show_wrong and k == "wrong":
                print("   WRONG %s/%s  wanted %s, said %s" % (d[:20], f, want, got))
        per[d] = n
        for k in n:
            tot[k] += n[k]
    return tot, per


def report(name, call, show_wrong=False):
    tot, per = score(call, show_wrong)
    print("%-34s right %3d   wrong %3d   unsure %3d" %
          (name, tot["right"], tot["wrong"], tot["unsure"]))
    for d, n in per.items():
        if n["wrong"] or n["unsure"]:
            print("      %-26s %3d / %3d / %3d" % (d[:26], n["right"], n["wrong"], n["unsure"]))


if __name__ == "__main__":
    report("what it does now", lambda b: sc.verdict(b)[0], "-v" in sys.argv)
