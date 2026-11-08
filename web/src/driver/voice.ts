import { PROMPTS } from "./voicePrompts";

export type Language = "hi" | "mr" | "en";
export type PromptId = keyof typeof PROMPTS;

/** Languages that have an audio file for every prompt, under public/voice/<language>/.
 * Marathi has none yet: this Mac has no Marathi voice to make them with, so Marathi is spoken by
 * the phone. A recording dropped in at the same path, plus "mr" here, replaces that. */
export const FILE_LANGUAGES: readonly Language[] = ["hi", "en"];

// Indian English, so the phone picks an Indian voice when it has one.
const SPEECH_LANG: Record<Language, string> = { hi: "hi-IN", mr: "mr-IN", en: "en-IN" };

export function voiceFileUrl(prompt: PromptId, language: Language): string {
  return `/voice/${language}/${prompt}.mp3`;
}

/** Every audio file the app has: each prompt in each language that has files. */
export function allVoiceFileUrls(): string[] {
  const prompts = Object.keys(PROMPTS) as PromptId[];
  return FILE_LANGUAGES.flatMap((language) =>
    prompts.map((prompt) => voiceFileUrl(prompt, language)),
  );
}

/** What a retake screen says. Blur and darkness have their own advice; anything else the driver
 * fixes the same way, by getting the whole receipt in a clear photo. */
export function retakePrompt(reasonCodes: string[]): PromptId {
  if (reasonCodes.includes("photo_blurred")) return "blurred";
  if (reasonCodes.includes("photo_dark")) return "dark";
  return "retake";
}

/** The browser's audio and speech, behind a small interface so tests can stand in for them. */
export interface Speaker {
  /** Resolves once playing starts. Rejects with the browser's DOMException if it can't. */
  playFile(url: string): Promise<void>;
  speak(text: string, lang: string): void;
  stop(): void;
}

export type Played = "file" | "speech" | "blocked" | "stopped";

/** Plays a prompt's audio file, or speaks its words if the file can't play: not cached while
 * offline, missing, or a format the phone can't decode. */
export async function playPrompt(
  prompt: PromptId,
  language: Language,
  speaker: Speaker,
): Promise<Played> {
  speaker.stop(); // One prompt at a time, so a quick tap doesn't talk over the last one.
  const words = PROMPTS[prompt][language];
  if (!FILE_LANGUAGES.includes(language)) {
    speaker.speak(words, SPEECH_LANG[language]);
    return "speech";
  }
  try {
    await speaker.playFile(voiceFileUrl(prompt, language));
    return "file";
  } catch (error) {
    const name = error instanceof DOMException ? error.name : "";
    // Before the driver's first tap the browser blocks all sound, speech included; the speaker
    // button is how they hear it then. AbortError means a newer prompt took over.
    if (name === "NotAllowedError") return "blocked";
    if (name === "AbortError") return "stopped";
    speaker.speak(words, SPEECH_LANG[language]);
    return "speech";
  }
}
