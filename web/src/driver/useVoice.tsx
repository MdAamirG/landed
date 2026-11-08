import { createContext, useCallback, useContext, useEffect } from "react";

import { allVoiceFileUrls, playPrompt, type Language, type PromptId, type Speaker } from "./voice";

// One audio element for the whole app. Phones allow sound only after a tap, and reusing the
// element the driver's tap unlocked keeps later prompts allowed too.
let audio: HTMLAudioElement | null = null;

const browserSpeaker: Speaker = {
  playFile(url) {
    audio ??= new Audio();
    audio.src = url;
    return audio.play();
  },
  speak(text, lang) {
    if (!("speechSynthesis" in window)) return; // No speech at all: the words are on screen.
    const words = new SpeechSynthesisUtterance(text);
    words.lang = lang;
    // The language alone usually picks the right voice. Naming one helps where the browser would
    // pick its default, but the list can be empty until the browser has loaded it.
    const voice = speechSynthesis.getVoices().find((v) => v.lang.replace("_", "-") === lang);
    if (voice) words.voice = voice;
    speechSynthesis.speak(words);
  },
  stop() {
    audio?.pause();
    if ("speechSynthesis" in window) speechSynthesis.cancel();
  },
};

const VOICE_CACHE = "landed-voice"; // public/sw.js serves /voice/ from this cache.

/** Stores every prompt's audio file on the phone, so prompts play in a dead zone. Each file is
 * fetched once; sw.js refreshes a stored one in the background when it plays with signal. */
export async function keepVoiceFilesOnPhone(): Promise<void> {
  try {
    const cache = await caches.open(VOICE_CACHE);
    for (const url of allVoiceFileUrls()) {
      if (!(await cache.match(url))) await cache.add(url);
    }
  } catch {
    // No signal or no Cache API: the prompts play from the network, or are spoken by the phone.
  }
}

type VoiceSettings = { language: Language; changeLanguage: (language: Language) => void };

export const VoiceContext = createContext<VoiceSettings>({
  language: "hi",
  changeLanguage: () => {},
});

/** Plays the screen's prompt when it opens, and again in a new language when the driver switches.
 * Returns a function that plays it again, for the speaker button. */
export function useVoicePrompt(prompt: PromptId): () => void {
  const { language } = useContext(VoiceContext);
  const play = useCallback(() => {
    void playPrompt(prompt, language, browserSpeaker);
  }, [prompt, language]);

  useEffect(() => {
    play();
    return () => browserSpeaker.stop(); // A prompt for a screen that's gone would mislead.
  }, [play]);

  return play;
}

export function SpeakerButton({ onPlay }: { onPlay: () => void }) {
  return (
    <button
      className="btn btn--card speaker"
      type="button"
      aria-label="Play voice instructions"
      onClick={onPlay}
    >
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M4 9h4l5-4v14l-5-4H4z" />
        <path d="M16.5 8.5a5 5 0 010 7M19 6a8.5 8.5 0 010 12" />
      </svg>
    </button>
  );
}

// Each language named in its own script, so a driver finds theirs without reading English.
const LANGUAGE_NAMES: [Language, string][] = [
  ["hi", "हिंदी"],
  ["mr", "मराठी"],
  ["en", "English"],
];

export function LanguageSwitch() {
  const { language, changeLanguage } = useContext(VoiceContext);
  return (
    <div className="groove" role="group" aria-label="Language">
      {LANGUAGE_NAMES.map(([code, name]) => (
        <button
          key={code}
          type="button"
          lang={code}
          aria-pressed={language === code}
          onClick={() => changeLanguage(code)}
        >
          {name}
        </button>
      ))}
    </div>
  );
}
