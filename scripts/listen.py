"""Turn sound into a score Claude can read: note onsets with pitch names, loudness and key.

A musician reading sheet music hears it in their head. Claude can't hear, but it can read
music, so the closest thing to ears is a good transcription made by plain arithmetic,
not by another model's opinion.

How: short-time spectrum; an onset is a jump in spectral energy (spectral flux); the pitch of
the NEW note is the strongest peak of what was added at that moment (spectrum after minus
before), so a note ringing on from earlier doesn't hide the new one. Key comes from the
12-bin pitch-class profile matched against major/minor templates (Krumhansl).

usage: python3 listen.py AUDIO [start_sec] [end_sec]
"""
import subprocess, sys
import numpy as np

SR, N, HOP = 22050, 4096, 256
NAMES = "C C# D D# E F F# G G# A A# B".split()

def load(path, t0=0.0, t1=None, track=None):
    """track: which audio stream to hear (0 = first); None lets ffmpeg pick."""
    cmd = ["ffmpeg", "-v", "error", "-ss", str(t0)] + (["-t", str(t1 - t0)] if t1 else []) + \
          ["-i", path] + (["-map", f"0:a:{track}"] if track is not None else []) + \
          ["-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.float32)

def note_name(f):
    m = 69 + 12 * np.log2(f / 440.0)
    k = int(round(m))
    return f"{NAMES[k % 12]}{k // 12 - 1}", m - k

def listen(x, t0=0.0):
    win = np.hanning(N)
    frames = np.lib.stride_tricks.sliding_window_view(x, N)[::HOP] * win
    S = np.abs(np.fft.rfft(frames, axis=1))
    freqs = np.fft.rfftfreq(N, 1 / SR)
    band = (freqs > 50) & (freqs < 2500)
    flux = np.maximum(S[1:, band] - S[:-1, band], 0).sum(axis=1)
    w = int(0.25 * SR / HOP)                        # local threshold: louder than its own neighbourhood
    floor = 0.05 * np.percentile(flux, 99)
    onsets = [i + 1 for i in range(1, len(flux) - 1)
              if flux[i] > max(floor, 1.5 * flux[max(0, i - w):i + w].mean())
              and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]]
    gap = int(0.06 * SR / HOP)                      # merge onsets closer than 60 ms
    kept = [o for j, o in enumerate(onsets) if j == 0 or o - onsets[j - 1] > gap]
    events = []
    for o in kept:
        after = S[min(o + 2, len(S) - 1)]
        before = S[max(o - 2, 0)]
        added = np.maximum(after - before, 0) * band
        k = int(added.argmax())
        if added[k] <= 0:
            continue
        # parabolic interpolation for a finer frequency than one FFT bin
        a, b, c = added[k - 1], added[k], added[k + 1]
        f = freqs[k] + 0.5 * (a - c) / (a - 2 * b + c + 1e-12) * (freqs[1] - freqs[0])
        # prefer the fundamental: if half the frequency also carries energy, take it
        k2 = int(round(k / 2))
        if k2 > 0 and band[k2] and added[k2 - 1:k2 + 2].max() > 0.35 * b:
            f /= 2
        rms = np.sqrt((x[o * HOP:o * HOP + N] ** 2).mean() + 1e-12)
        events.append((t0 + (o * HOP + N / 2) / SR, f, 20 * np.log10(rms)))   # window centre, not start
    # key from the pitch-class profile of the whole excerpt
    pc = np.zeros(12)
    for i, f in enumerate(freqs):
        if 60 < f < 2000:
            pc[int(round(69 + 12 * np.log2(f / 440))) % 12] += S[:, i].sum()
    major = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    best = max(((np.corrcoef(np.roll(t, r), pc)[0, 1], f"{NAMES[r]} {name}")
                for t, name in ((major, "major"), (minor, "minor")) for r in range(12)))
    return events, best[1]

if __name__ == "__main__":
    t0 = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    t1 = float(sys.argv[3]) if len(sys.argv) > 3 else None
    ev, key = listen(load(sys.argv[1], t0, t1), t0)
    print(f"key ~ {key}; {len(ev)} note onsets")
    for t, f, db in ev:
        name, cents = note_name(f)
        print(f"{t:7.2f}s  {name:4s} {cents * 100:+4.0f}c  {db:6.1f} dB")


def chords(x, t0=0.0, step=1.0):
    """One chord name per `step` seconds from the pitch-class profile (major/minor triads only).
    Also returns the lowest strong pitch (bass) for each step; '·' means near silence."""
    out = []
    n = int(step * SR)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    ok = (freqs > 55) & (freqs < 2000)
    pcs = (np.round(69 + 12 * np.log2(np.where(ok, freqs, 440) / 440)).astype(int)) % 12
    tmpl = []
    for r in range(12):
        for name, iv in (("", (0, 4, 7)), ("m", (0, 3, 7))):
            v = np.zeros(12); v[[(r + i) % 12 for i in iv]] = 1
            tmpl.append((NAMES[r] + name, v / np.linalg.norm(v)))
    for k in range(0, len(x) - n + 1, n):
        seg = x[k:k + n] * np.hanning(n)
        mag = np.abs(np.fft.rfft(seg))
        if np.sqrt((x[k:k + n] ** 2).mean()) < 1e-3:
            out.append((t0 + k / SR, "·", "·")); continue
        pc = np.bincount(pcs[ok], weights=mag[ok] ** 2, minlength=12)
        pc /= np.linalg.norm(pc) + 1e-12
        name = max(tmpl, key=lambda t: t[1] @ pc)[0]
        low = (freqs > 55) & (freqs < 250)          # below 55 Hz it is mostly rumble
        bass = note_name(freqs[low][mag[low].argmax()])[0]
        out.append((t0 + k / SR, name, bass))
    return out
