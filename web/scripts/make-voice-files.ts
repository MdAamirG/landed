// Makes the voice prompt audio files in public/voice/ from src/driver/voicePrompts.ts.
// Run it on a Mac after changing a prompt's words: npm run voice-files
//
// It uses the voices built into macOS, which are free and need no account or network. There is
// no macOS Marathi voice, so Marathi gets no files and the phone speaks it instead (see
// FILE_LANGUAGES in src/driver/voice.ts). A native speaker's recording is better than any of
// these: save it as public/voice/<language>/<prompt>.mp3 and stop running this for that language.
//
// Node 23.6 or later runs TypeScript directly, so this needs no build step.

import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { PROMPTS } from "../src/driver/voicePrompts.ts";

// The macOS voice for each language that gets files. Lekha is Hindi; Rishi is Indian English.
const VOICES = { hi: "Lekha", en: "Rishi" } as const;

const OUT = fileURLToPath(new URL("../public/voice/", import.meta.url));
const scratch = mkdtempSync(join(tmpdir(), "landed-voice-"));

try {
  for (const [language, voice] of Object.entries(VOICES)) {
    mkdirSync(join(OUT, language), { recursive: true });
    for (const [prompt, words] of Object.entries(PROMPTS)) {
      const aiff = join(scratch, `${language}-${prompt}.aiff`);
      const mp3 = join(OUT, language, `${prompt}.mp3`);
      // execFileSync passes the words as one argument, with no shell to mangle the Devanagari.
      execFileSync("say", ["-v", voice, "-o", aiff, words[language as keyof typeof VOICES]]);
      // Mono speech at 48 kbps is clear on a phone speaker and keeps each file near 30 KB, so
      // caching all of them for offline use costs the driver very little data.
      execFileSync("ffmpeg", [
        "-y",
        "-loglevel", "error",
        "-i", aiff,
        "-ac", "1",
        "-ar", "22050",
        "-codec:a", "libmp3lame",
        "-b:a", "48k",
        "-map_metadata", "-1", // No tool or date tags, so re-running gives the same file.
        mp3,
      ]);
      console.log(mp3);
    }
  }
} finally {
  rmSync(scratch, { recursive: true, force: true });
}
