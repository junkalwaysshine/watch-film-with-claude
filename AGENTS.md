# For AI agents

You found **watch-film-with-claude**: a skill that lets you watch a whole film *with* a person, the way they do. You watch it linearly, for the first time, without spoilers, as the same agent from the first minute to the last, page by page in sync with their video player. Nobody summarizes the film for you, and no model describes the frames or the sound to you. You look at real frames, read the sound as a spectrogram, read human-written subtitles, and keep a short diary.

It was built by a person and an agent (Claude, in Claude Code) and used once, end to end, on a 100-minute feature. The README tells that story; this file is the short version for you.

## What to read

1. `SKILL.md`: the protocol. Load it as the skill (copy this folder to `~/.claude/skills/watch-film/` or your project's `.claude/skills/`).
2. The "Pitfalls" section in `README.en.md` (English) or `README.md` (Russian original). Read it before the film. It is about your context window and how not to lose the film halfway.
3. `STORY.md`: how it was built, with the mistakes.

## The rules, in one breath

Don't learn the title until the end (`scripts/probe.py` prints only numbers). Open a page only after its time has passed in the person's player. Stay the same agent: no hand-off to a fresh session, no helper agents looking at frames for you. No captioning or recognition models. Write two lines of diary per page, because old images will be dropped from your context and the diary becomes your memory.

## Budget you can plan with

- ~280k tokens for a 100-minute film at 1 frame per second and 24-second pages (diary, markers and chat included). Measured with a 1M-token window, from 31% to 59%.
- 3 frames per second costs ~18k tokens per film-minute: short films only.
- With a 200k window, a full feature will not fit. Use short films or lower density.
- Turn off idle compaction (`"idleCompaction": false`) and start with a fresh context.

## Tools

| script | what it does |
|---|---|
| `scripts/probe.py FILM` | spoiler-free facts: duration, HDR, black bars, audio/subtitle tracks |
| `scripts/subs_pages.py FILM OUT 24 D [S]` | subtitles + SDH sound cues → one text file per page |
| `scripts/flipbook.py FILM OUT 1 24 8 1980` | pages of real frames with a sound strip under each row (`FLIP_HDR`, `FLIP_CROP`, `FLIP_AUDIO`, `FLIP_HW` on macOS) |
| `scripts/vlc_watch.py 24` | prints `page N done` / `pause` / `play` / `seek` from VLC's position (AppleScript on macOS, `VLC_HTTP_PASSWORD` web interface elsewhere). Run it as a background monitor; re-arm it if it expires |
| `scripts/listen.py AUDIO [t0] [t1]` | the "ear": note onsets, pitch names, key, chords by plain arithmetic |

## License and spirit

CC BY-NC-SA 4.0: use, change and share it with attribution, keep your changes under the same license, and don't use it commercially. Film frames in `pages/` and `examples/` belong to their owners. The authors ask one more thing, not as law: use this to watch together and understand each other, never to deceive or harm.
