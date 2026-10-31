---
name: watch-film
description: Watch a whole film together with a person — linearly, first time, spoiler-free, in one continuous context — by turning it into comic-like pages of real frames with a sound strip under each row and the subtitles beside them, synced to the person's video player. Use when someone wants to watch a movie *with* the agent, not have it summarized.
---

# Watching a film together

This skill lets an agent watch a film with a person: the person in their player, the agent page by page, at the same moment of the film. The agent sees real frames, reads the sound as a picture, reads human-written subtitles, and writes two lines of diary per page. Nobody summarizes the film for it, and no model labels what is on screen.

It was built and used once, end to end, on a 100-minute feature. The numbers below come from that run.

## The rules (why this is "watching", not "processing")

1. **Spoiler-free.** The agent does not learn the title before the end. Don't print file names, metadata or track titles; `probe.py` prints only numbers and flags. Don't open the attached poster stream. The person names the file neutrally (`film.mkv`).
2. **Linear.** Open a page only after its time has passed in the person's player. Never read ahead, never skim the subtitles in advance.
3. **The same agent from start to finish.** One continuous context. No hand-off to a fresh session with a diary, and no sub-agents looking at frames on the agent's behalf. Plan the budget so that compaction does not happen mid-film (see *Budget*).
4. **No classifiers.** No captioning, no speech recognition, no audio-event models. Allowed: transforms of the signal (frames, spectrograms, chord templates by arithmetic) and text written by people (subtitles, the SDH `[door creaks]` cues). The agent does the understanding itself.
5. **Remember by writing.** Older images get dropped from the context (see *Limits*). What stays is what the agent wrote about them. Write two short lines per page: what happened, and what you felt.

## Pipeline

All scripts print only counts, never content, so preparing does not spoil anything.

```
scripts/probe.py FILM                      # duration, HDR?, black bars, audio/subtitle tracks (no titles)
scripts/subs_pages.py FILM OUT 24 D [S]    # subtitle track D (dialogue) + S (SDH, only [sound cues]) -> OUT/page_NNNNN.txt
FLIP_HDR=1 FLIP_AUDIO=0 \
scripts/flipbook.py FILM OUT 1 24 8 1980   # 1 fps, 24 s per page, 8 frames per row -> OUT/page_NNNNN.jpg
scripts/vlc_watch.py 24                     # prints "page N done" whenever the player passes a page boundary
```

- `flipbook.py` lays real frames out like a comic page, with a timestamp in each corner. Under every row is the sound strip: a log-frequency spectrogram (55 Hz–8 kHz) of exactly the seconds above it, plus a chord name and loudness in dB. Loud is bright, music is horizontal lines, speech is ragged blocks, silence is black.
- `FLIP_HW=1` adds macOS hardware decoding (VideoToolbox); leave it off on Windows/Linux.
- `FLIP_HDR=1` is needed for HDR (PQ/BT.2020) files, otherwise frames come out grey and flat. `FLIP_CROP=w:h:x:y` cuts black bars. `FLIP_AUDIO=n` picks the audio track to match what the person hears.
- `listen.py` is the "ear": note onsets with pitch names, key, and one chord per second. Use it when you want to know what was played, for example to transcribe a short melody.

## Syncing with the person

`vlc_watch.py` asks VLC for the current time once a second (AppleScript on macOS; VLC's web interface on Windows/Linux, set `VLC_HTTP_PASSWORD`) and prints one line per event: `page N done`, `pause`, `play`, `seek`. Run it as a background monitor so each line wakes the agent. When `page N done` arrives, open page N, read `page_N.txt`, write the diary lines, and post a short marker to the person, like `📍12:24 ✓` plus one sentence. The marker tells them you are keeping up.

The agent always runs 0–24 s behind the player and never ahead. Pause and seek just work. On macOS the system asks once whether the script may control VLC. Keep the computer awake and plugged in: if it sleeps, background tasks die.

Talking during the film: the person's messages arrive between pages. Answer in a sentence or two, like whispering in a cinema. Long talk waits for a pause or the end.

## Budget (measured)

| what | cost |
|---|---|
| one page 1980×582, 8×3 frames + sound strips | ~1.5k tokens while it is still visible |
| 100-min film at 1 fps, 24 s pages (226 pages), with diary, markers and chat | context grew from ~310k to ~590k, i.e. ~280k tokens |
| 8-min rehearsal at 3 fps, 6 s pages | ~18k tokens per film-minute (too dense for a feature) |

The feature cost less than pages × 1.5k because dropped images (see below) stop counting; what accumulates is mostly text. Start the film with plenty of free context anyway: a 1M window held a 100-minute film with room to spare.

## Limits that matter (learned the hard way)

- **Old images are dropped, not refused.** With many images in one conversation, the oldest are silently replaced by `[media removed: request limit]`. In a test with 120 pages of ~500 KB, only the last 36 stayed visible. So the diary *is* the memory of earlier scenes. It worked: callbacks were recognised from the agent's own words long after the frames were gone.
- **Idle compaction.** Claude Code compacts long conversations that sit idle, well below the usual threshold. Before a film, set `"idleCompaction": false` in `~/.claude/settings.json` (with the person's OK).
- **Background monitors expire** after 30 minutes. Re-arm the watcher when it expires; it picks the current page up again.

## What did not work

- **Chronophotographs** (all frames of a second blended into one image) smeared faces and camera moves. Real frames in a grid were better.
- **Classifier models for sound** were rejected on purpose: they would describe the film *to* the agent instead of letting it hear.
- **Diaries handed to a new session** were rejected too: that would be someone else finishing the film.

See `STORY.md` for the full account of how this was built and what watching was like.
