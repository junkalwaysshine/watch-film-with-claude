"""Look at a film file without spoiling it: prints only numbers and flags, never titles or tags.

Shows duration, video size, whether it is HDR, black bars, and the audio/subtitle tracks
(language + kind words like "forced", "sdh", "full", "commentary"), so you can choose
which audio track to hear and which subtitle tracks to read. Track titles and file metadata
are not printed, because they often contain the film's name.

usage: python3 probe.py FILM
"""
import json, subprocess, sys

film = sys.argv[1]
info = json.loads(subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries",
     "format=duration:stream=index,codec_type,codec_name,channels,width,height,color_transfer"
     ":stream_tags=language,title:stream_disposition=default,attached_pic",
     "-of", "json", film], capture_output=True, text=True).stdout)

dur = float(info["format"]["duration"])
print(f"duration_min {dur / 60:.1f}")
counts = {"video": 0, "audio": 0, "subtitle": 0}
for s in info["streams"]:
    kind, tags, disp = s["codec_type"], s.get("tags", {}), s.get("disposition", {})
    if kind not in counts:
        continue
    n = counts[kind]
    counts[kind] += 1
    if disp.get("attached_pic"):
        print(f"{kind}:{n} attached poster image (skip it, it may show the title)")
        continue
    title = (tags.get("title") or "").lower()
    words = [w for w in ("forced", "sdh", "full", "comment", "dub", "signs") if w in title]
    extra = ""
    if kind == "video":
        hdr = s.get("color_transfer") in ("smpte2084", "arib-std-b67")
        extra = f"{s.get('width')}x{s.get('height')} {'HDR -> set FLIP_HDR=1' if hdr else 'SDR'}"
    elif kind == "audio":
        extra = f"channels={s.get('channels')}"
    print(f"{kind}:{n} lang={tags.get('language', '?')} {'default ' if disp.get('default') else ''}"
          f"{extra} kind={','.join(words) or '-'}")

# black bars: sample four points of the film, print only the crop numbers
for frac in (0.2, 0.4, 0.6, 0.8):
    out = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(dur * frac), "-i", film, "-map", "0:v:0",
                          "-t", "3", "-vf", "cropdetect=24:2:0", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    crops = [w for w in out.split() if w.startswith("crop=")]
    print(f"cropdetect@{int(frac * 100)}% {crops[-1] if crops else '?'}")
