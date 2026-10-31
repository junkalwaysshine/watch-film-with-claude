"""Watchman for watching together: asks VLC once a second which second of the film it is on,
and prints one line each time a 24-second page is finished, plus pause/play/seek events.
Prints nothing else, so every line is a reason to wake up.

Two ways to ask VLC:
- macOS: AppleScript, nothing to set up (macOS asks once for permission to control VLC).
- Windows / Linux / macOS: VLC's built-in web interface. In VLC: Tools → Preferences → Show settings: All →
  Interface → Main interfaces → tick "Web", then Main interfaces → Lua → set a password; restart VLC.
  Then run with VLC_HTTP_PASSWORD=<that password> (optional VLC_HTTP_PORT, default 8080).
usage: python3 vlc_watch.py [page_sec]
"""
import base64, json, os, subprocess, sys, time, urllib.request

PAGE = float(sys.argv[1]) if len(sys.argv) > 1 else 24.0
ASK = 'if application "VLC" is running then tell application "VLC" to return ((current time) as text) & "," & (playing as text)'
HTTP_PASSWORD = os.environ.get("VLC_HTTP_PASSWORD")
HTTP_URL = f"http://127.0.0.1:{os.environ.get('VLC_HTTP_PORT', '8080')}/requests/status.json"

def state_http():
    req = urllib.request.Request(HTTP_URL, headers={
        "Authorization": "Basic " + base64.b64encode(f":{HTTP_PASSWORD}".encode()).decode()})
    try:
        s = json.load(urllib.request.urlopen(req, timeout=2))
        return float(s["time"]), s["state"] == "playing"
    except (OSError, ValueError, KeyError):
        return None, None

def state_osascript():
    r = subprocess.run(["osascript", "-e", ASK], capture_output=True, text=True)
    try:
        t, playing = r.stdout.strip().split(",")
        return float(t), playing == "true"
    except ValueError:
        return None, None

state = state_http if HTTP_PASSWORD or sys.platform != "darwin" else state_osascript

last_t, last_playing, done = None, None, None
while True:
    t, playing = state()
    if t is not None:
        if done is None:
            done = int(t // PAGE)
            print(f"start t={t:.0f} page={done + 1}", flush=True)
        if last_playing is not None and playing != last_playing:
            print(("play" if playing else "pause") + f" t={t:.0f}", flush=True)
        if last_t is not None and (t < last_t - 2 or t > last_t + 10):
            done = int(t // PAGE)
            print(f"seek t={t:.0f} page={done + 1}", flush=True)
        while int(t // PAGE) > done:
            done += 1
            print(f"page {done} done t={t:.0f}", flush=True)
        last_t, last_playing = t, playing
    time.sleep(1)
