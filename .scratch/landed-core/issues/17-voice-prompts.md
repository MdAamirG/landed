# 17: Voice prompts

**What to build:** Drivers hear about 8 short prompts in Hindi or Marathi, with a language switch and a speaker button to replay them. Prompts are cached so they work offline, and browser speech is the fallback.

**Blocked by:** 08

**Status:** done, except the speaker check, which is ready-for-human

**Scheduled:** Only if time remains

**Spec stories:** 7, 8

- [x] About 8 prompts exist as cached audio files in Hindi and Marathi. Nine prompts; Hindi and English have files from macOS voices, and Marathi is spoken by the phone because macOS has no Marathi voice (spec assumption 38)
- [x] The language starts from `drivers.language`, and the switch changes it
- [x] The speaker button replays the current prompt
- [x] Browser speech is used if an audio file can't play
- [ ] A Hindi and Marathi speaker's check is recorded before this is called done (ready-for-human: record it in `docs/voice-prompts.md`)
