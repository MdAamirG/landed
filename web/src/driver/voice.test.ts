import { describe, expect, it } from "vitest";

import { allVoiceFileUrls, playPrompt, retakePrompt, type Speaker } from "./voice";

/** A speaker that records what it was asked to do. playFile fails with errorName, if given. */
function fakeSpeaker(errorName?: string) {
  const calls: string[] = [];
  const speaker: Speaker = {
    async playFile(url) {
      calls.push(`file ${url}`);
      if (errorName) throw new DOMException("could not play", errorName);
    },
    speak(text, lang) {
      calls.push(`speak ${lang} ${text}`);
    },
    stop() {
      calls.push("stop");
    },
  };
  return { speaker, calls };
}

describe("which prompt a retake plays", () => {
  it("says to hold still for a blurred photo", () => {
    expect(retakePrompt(["photo_blurred"])).toBe("blurred");
  });

  it("says to find light for a dark photo", () => {
    expect(retakePrompt(["photo_dark", "stamp_missing"])).toBe("dark");
  });

  it("asks for the photo again for anything else", () => {
    expect(retakePrompt(["stamp_missing"])).toBe("retake");
    expect(retakePrompt([])).toBe("retake");
  });
});

describe("playing a prompt", () => {
  it("plays the Hindi file, after stopping whatever was playing", async () => {
    const { speaker, calls } = fakeSpeaker();

    expect(await playPrompt("take_photo", "hi", speaker)).toBe("file");
    expect(calls).toEqual(["stop", "file /voice/hi/take_photo.mp3"]);
  });

  it("speaks the prompt when the file can't play", async () => {
    const { speaker, calls } = fakeSpeaker("NotSupportedError");

    expect(await playPrompt("checking", "hi", speaker)).toBe("speech");
    expect(calls).toEqual([
      "stop",
      "file /voice/hi/checking.mp3",
      "speak hi-IN फोटो की जाँच हो रही है। कृपया गेट पर रुकें।",
    ]);
  });

  it("stays silent when the browser blocks sound until the driver taps", async () => {
    // Speech would be blocked too. The speaker button is how the driver hears it.
    const { speaker, calls } = fakeSpeaker("NotAllowedError");

    expect(await playPrompt("take_photo", "hi", speaker)).toBe("blocked");
    expect(calls).toEqual(["stop", "file /voice/hi/take_photo.mp3"]);
  });

  it("stays silent when a newer prompt cut this one off", async () => {
    const { speaker, calls } = fakeSpeaker("AbortError");

    expect(await playPrompt("take_photo", "hi", speaker)).toBe("stopped");
    expect(calls).toEqual(["stop", "file /voice/hi/take_photo.mp3"]);
  });

  it("speaks Marathi straight away, because Marathi has no files yet", async () => {
    const { speaker, calls } = fakeSpeaker();

    expect(await playPrompt("verified", "mr", speaker)).toBe("speech");
    expect(calls).toEqual(["stop", "speak mr-IN पीओडी बरोबर आहे. तुम्ही जाऊ शकता."]);
  });
});

describe("the audio files", () => {
  it("exist for every prompt in every language that claims them", () => {
    // Vite lists the files at build time; the keys are paths from this folder.
    const onDisk = Object.keys(import.meta.glob("../../public/voice/*/*.mp3")).map((path) =>
      path.replace("../../public", ""),
    );
    const missing = allVoiceFileUrls().filter((url) => !onDisk.includes(url));

    expect(missing).toEqual([]);
  });
});
