"""Measure time-to-first-audio, old path against new, on the same server.

Kokoro renders roughly twice as fast as the audio plays on this machine's CPU
(the build note's measured 1.0-1.3s for a short sentence). The stand-in below
holds to that: it emits PCM in chunks, paced, exactly as the real server does.
What is being measured is the CLIENT - whether it waits for the whole sentence
before a sample reaches the speakers, or plays on a banked head while the rest
arrives. That is the half that changed.
"""
import http.server
import json
import os
import queue
import socketserver
import sys
import threading
import time
import types

import numpy as np

RATE = 24000
RENDER_SPEED = 2.0          # renders at 2x realtime
CHUNK_MS = 100              # the server emits ~100ms of audio at a time


class Kokoro(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        words = max(1, len(body["input"].split()))
        seconds = words / 2.6                     # ~156 wpm, a spoken pace
        total = int(RATE * seconds)
        chunk = int(RATE * CHUNK_MS / 1000)
        self.send_response(200)
        self.send_header("Content-Type", "audio/pcm")
        self.end_headers()
        done = 0
        while done < total:
            n = min(chunk, total - done)
            t = np.arange(done, done + n) / RATE
            pcm = (np.sin(2 * np.pi * 180 * t) * 6000).astype(np.int16)
            time.sleep((n / RATE) / RENDER_SPEED)   # the render cost
            try:
                self.wfile.write(pcm.tobytes())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
            done += n


def serve(port):
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", port), Kokoro)
    srv.allow_reuse_address = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# --- stub the audio device, and stamp the first write ------------------------
FIRST = {"at": None}
WRITES = []


class FakeStream:
    def __init__(self, **k): self.stopped = False
    def start(self): self.stopped = False
    def stop(self): self.stopped = True
    def close(self): pass
    def abort(self): pass
    def write(self, chunk):
        if FIRST["at"] is None:
            FIRST["at"] = time.time()
        WRITES.append(len(chunk))
        # playing takes real time, which is what lets the stream get ahead
        time.sleep(len(chunk) / RATE)


sd = types.ModuleType("sounddevice")
sd.OutputStream = lambda **k: FakeStream()
sd.InputStream = lambda **k: FakeStream()
sd.default = types.SimpleNamespace(device=(None, None))
sd.query_devices = lambda *a: []
sys.modules["sounddevice"] = sd

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
os.environ["ETHEREAL_KOKORO_URL"] = f"http://127.0.0.1:{PORT}/v1/audio/speech"
os.environ.setdefault("ETHEREAL_BUS_DIR", "/tmp/bench-bus")
os.environ.setdefault("ETHEREAL_VOICE_SETTINGS", "/tmp/bench-settings.json")
os.environ["ETHEREAL_DUCKING"] = "0"
sys.path.insert(0, "/home/trism/Ethereal/voice-line")

serve(PORT)
import config  # noqa: E402
import mouth as mouth_mod  # noqa: E402

SHORT = "The note is written, sir."
LONG = ("The note is written and verified, sir, and I have folded the correction "
        "into the job that governs it rather than leaving it in the daily record, "
        "where no future session would have read it before doing that work again.")


def measure(sentence, streaming):
    FIRST["at"] = None
    WRITES.clear()
    m = mouth_mod.Mouth()
    m.begin_turn()
    if not streaming:
        # the OLD path: ask for the whole body, then play it
        import requests
        orig = m._synthesize_stream

        def whole(s):
            r = requests.post(config.KOKORO_URL, json={
                "model": "kokoro", "input": s, "voice": config.VOICE,
                "response_format": "pcm", "speed": config.SPEED}, timeout=90)
            r.raise_for_status()
            yield np.frombuffer(r.content, dtype=np.int16)
        m._synthesize_stream = whole
    t0 = time.time()
    m.say_chunk(sentence)
    while FIRST["at"] is None and time.time() - t0 < 30:
        time.sleep(0.005)
    first = (FIRST["at"] - t0) if FIRST["at"] else float("nan")
    m.interrupt()
    return first


print(f"prebuffer = {config.TTS_PREBUFFER}s   stand-in renders at {RENDER_SPEED}x realtime\n")
print(f"{'sentence':10} {'spoken length':>14} {'OLD (whole body)':>18} {'NEW (streamed)':>16} {'saved':>9}")
for label, text in (("short", SHORT), ("long", LONG)):
    spoken = len(text.split()) / 2.6
    old = measure(text, streaming=False)
    time.sleep(0.3)
    new = measure(text, streaming=True)
    print(f"{label:10} {spoken:13.1f}s {old:17.2f}s {new:15.2f}s {old-new:8.2f}s")
