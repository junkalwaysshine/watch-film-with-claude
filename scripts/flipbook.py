"""Flipbook pages: real frames only, no blending, laid out like a comic page.

Takes FPS frames per second (24 = every single frame) and tiles them in reading order,
left to right, top to bottom, COLS tiles per row, PAGE_SEC seconds per page.
A small timestamp sits in each tile's corner. Prints only counts.

usage: python3 flipbook.py VIDEO OUTDIR fps page_sec [cols] [page_width] [start_sec] [end_sec]
"""
import os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

video, out = sys.argv[1], sys.argv[2]
fps, page_sec = int(sys.argv[3]), int(sys.argv[4])
cols = int(sys.argv[5]) if len(sys.argv) > 5 else 6
page_w = int(sys.argv[6]) if len(sys.argv) > 6 else 1980
t0 = float(sys.argv[7]) if len(sys.argv) > 7 else 0.0
t1 = float(sys.argv[8]) if len(sys.argv) > 8 else None
os.makedirs(out, exist_ok=True)

w0, h0 = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                  "stream=width,height", "-of", "csv=p=0", video],
                                 capture_output=True, text=True).stdout.strip().strip(",").split(",")[:2])
# Optional, for real films: FLIP_CROP="w:h:x:y" cuts black bars (from cropdetect numbers),
# FLIP_HW=1 decodes on the Mac's video hardware; the video stream is always the first one,
# so an attached poster image is never used.
crop = os.environ.get("FLIP_CROP")
if crop:
    w0, h0 = map(int, crop.split(":")[:2])
tw = page_w // cols
th = int(round(tw * h0 / w0 / 2)) * 2
# FLIP_HDR=1: the film is HDR (PQ, BT.2020). Plain conversion leaves it grey and washed out,
# and this ffmpeg has no zscale, so tone-map here: PQ -> nits -> BT.709 -> Reinhard -> gamma.
hdr = bool(os.environ.get("FLIP_HDR"))
vf = (f"crop={crop}," if crop else "") + f"fps={fps},scale={tw}:{th}" + \
     (":in_color_matrix=bt2020:in_range=tv" if hdr else "")
cmd = ["ffmpeg", "-v", "error"] + (["-hwaccel", "videotoolbox"] if os.environ.get("FLIP_HW") else []) + \
      ["-ss", str(t0)] + (["-t", str(t1 - t0)] if t1 else []) + \
      ["-i", video, "-map", "0:v:0", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb48le" if hdr else "rgb24", "-"]
BT2020_TO_709 = np.array([[1.6605, -0.5876, -0.0728], [-0.1246, 1.1329, -0.0083], [-0.0182, -0.1006, 1.1187]])

def tonemap(raw):
    e = np.frombuffer(raw, np.uint16).reshape(th, tw, 3) / 65535.0
    p = e ** (1 / 78.84375)
    nits = 10000 * (np.maximum(p - 0.8359375, 0) / (18.8515625 - 18.6875 * p)) ** (1 / 0.1593017578125)
    lin = np.clip((nits / 100.0) @ BT2020_TO_709.T, 0, None)        # 100 nits = SDR white
    lum = lin @ [0.2126, 0.7152, 0.0722]
    scale = (1 + lum / 100.0) / (1 + lum)                           # Reinhard, white point 1000 nits
    out = np.clip(lin * scale[..., None], 0, 1) ** (1 / 2.4)
    return (out * 255).astype(np.uint8)
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
per_page = fps * page_sec
rows = -(-per_page // cols)
SH = 56                                           # height of the sound strip under each row of frames

# Sound strip: like the optical soundtrack printed beside the frames on real film stock.
# Under every row of frames lies the spectrogram of exactly the time those frames cover
# (log frequency 55 Hz..8 kHz bottom to top, brightness = loudness), plus that row's chord and level.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import listen
audio = listen.load(video, t0, t1, int(os.environ["FLIP_AUDIO"]) if "FLIP_AUDIO" in os.environ else None)
ASR = listen.SR
LO, HI = np.log2(55), np.log2(8000)

def sound_strip(a, b, width):
    seg = audio[int(a * ASR):int(b * ASR)]
    strip = np.zeros((SH, width, 3), np.uint8)
    if len(seg) < 1024:
        return strip, "·", -99.0
    hop = max(1, (len(seg) - 1024) // width)
    fr = np.lib.stride_tricks.sliding_window_view(seg, 1024)[::hop][:width] * np.hanning(1024)
    mag = np.abs(np.fft.rfft(fr, axis=1)) / 512      # amplitude scale (hann window sum)
    f = np.fft.rfftfreq(1024, 1 / ASR)
    rowsf = np.clip(((np.log2(np.maximum(f, 1)) - LO) / (HI - LO) * SH).astype(int), -1, SH)
    img = np.zeros((SH, mag.shape[0]))
    for k in range(SH):
        sel = rowsf == k
        if sel.any():
            img[SH - 1 - k] = mag[:, sel].max(axis=1)
    img = np.clip((20 * np.log10(img + 1e-7) + 80) / 60, 0, 1)    # -80..-20 dB -> 0..1
    col = np.stack([img ** 0.6, img ** 1.6, 0.25 * img + 0.15 * img ** 3], -1)
    strip[:, :img.shape[1]] = (col * 255).astype(np.uint8)
    chord = listen.chords(seg, 0, len(seg) / ASR)[0][1]
    db = 20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9)
    return strip, chord, db

def save(tiles, first_index, page_no):
    page = Image.new("RGB", (cols * tw, rows * (th + SH)), (0, 0, 0))
    d = ImageDraw.Draw(page)
    for r in range(-(-len(tiles) // cols)):
        a = (first_index + r * cols) / fps
        b = (first_index + min(len(tiles), (r + 1) * cols)) / fps
        strip, chord, db = sound_strip(a, b, cols * tw)
        y = r * (th + SH) + th
        page.paste(Image.fromarray(strip), (0, y))
        d.rectangle([0, y, 92, y + 11], fill=(0, 0, 0))
        d.text((2, y), "%s %4.0fdB" % (chord, db), fill=(120, 255, 160))
    for i, t in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th + SH)
        page.paste(Image.fromarray(t), (x, y))
        sec = t0 + (first_index + i) / fps
        lab = "%d:%02d.%02d" % (sec // 60, sec % 60, round((sec % 1) * 100) % 100)
        d.rectangle([x, y, x + 50, y + 11], fill=(0, 0, 0))
        d.text((x + 2, y), lab, fill=(255, 255, 0))
    page.save(os.path.join(out, "page_%05d.jpg" % page_no), quality=86)

tiles, n, page_no = [], 0, 0
while True:
    nbytes = tw * th * (6 if hdr else 3)
    raw = proc.stdout.read(nbytes)
    if len(raw) < nbytes:
        break
    tiles.append(tonemap(raw) if hdr else np.frombuffer(raw, np.uint8).reshape(th, tw, 3))
    if len(tiles) == per_page:
        page_no += 1; save(tiles, n, page_no); n += len(tiles); tiles = []
if tiles:
    page_no += 1; save(tiles, n, page_no)
proc.wait()
print(f"pages={page_no} tile={tw}x{th} page={cols * tw}x{rows * (th + SH)}")
