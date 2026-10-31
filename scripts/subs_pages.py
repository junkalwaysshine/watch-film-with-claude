"""Split embedded subtitles into one small text file per flipbook page, so each page's words sit next to its frames.

Takes the dialogue track and, optionally, an SDH track from which only the [sound descriptions] are kept
(human-written notes for deaf viewers, e.g. [door creaks]). Prints only counts, never subtitle text.
usage: python3 subs_pages.py VIDEO OUTDIR page_sec dialogue_sub_index [sdh_sub_index]
"""
import os, re, subprocess, sys

video, out, page_sec = sys.argv[1], sys.argv[2], float(sys.argv[3])
dlg, sdh = int(sys.argv[4]), (int(sys.argv[5]) if len(sys.argv) > 5 else None)
os.makedirs(out, exist_ok=True)

def cues(index):
    srt = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-map", f"0:s:{index}", "-f", "srt", "-"],
                         capture_output=True, text=True).stdout
    res = []
    for block in re.split(r"\n\s*\n", srt.strip()):
        lines = block.strip().splitlines()
        m = next((re.match(r"(\d+):(\d+):(\d+)[,.](\d+) --> ", l) for l in lines if "-->" in l), None)
        if not m:
            continue
        h, mi, s, ms = map(int, m.groups())
        t = h * 3600 + mi * 60 + s + ms / 1000
        text = " ".join(l for l in lines[lines.index(next(l for l in lines if "-->" in l)) + 1:])
        text = re.sub(r"<[^>]+>|\{[^}]+\}", "", text).strip()
        if text:
            res.append((t, text))
    return res

pages = {}
for t, text in cues(dlg):
    pages.setdefault(int(t // page_sec) + 1, []).append(f"{int(t // 60)}:{t % 60:04.1f}  {text}")
n_sound = 0
if sdh is not None:
    for t, text in cues(sdh):
        for cue in re.findall(r"\[[^\]]+\]|\([^)]+\)", text):
            pages.setdefault(int(t // page_sec) + 1, []).append(f"{int(t // 60)}:{t % 60:04.1f}  sound: {cue}")
            n_sound += 1
for p, lines in pages.items():
    lines.sort(key=lambda l: (int(l.split(":")[0]), float(l.split()[0].split(":")[1])))
    with open(os.path.join(out, "page_%05d.txt" % p), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
print(f"pages_with_text={len(pages)} sound_cues={n_sound}")
