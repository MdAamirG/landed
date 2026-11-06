# 17: Voice prompts

**What to build:** Drivers hear about 8 short prompts in Hindi or Marathi, with a language switch and a speaker button to replay them. Prompts are cached so they work offline, and browser speech is the fallback.

**Blocked by:** 08

**Status:** ready-for-agent

**Scheduled:** Only if time remains

**Spec stories:** 7, 8

- [ ] About 8 prompts exist as cached audio files in Hindi and Marathi
- [ ] The language starts from `drivers.language`, and the switch changes it
- [ ] The speaker button replays the current prompt
- [ ] Browser speech is used if an audio file can't play
- [ ] A Hindi and Marathi speaker's check is recorded before this is called done
