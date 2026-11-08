import { useMemo } from "react";

import type { DriverTrip } from "../lib/api";
import type { PhotoProblem } from "./capture";
import { SpeakerButton, useVoicePrompt } from "./useVoice";

const PROBLEM_TEXT: Record<PhotoProblem, string> = {
  blurred: "The photo is blurred. Hold the phone still.",
  dark: "The photo is too dark. Move to the light.",
};

/** The phone itself found a problem, so this costs no retake and needs no network. */
export default function PhoneCheckFailed({
  trip,
  photo,
  problem,
  canSendAnyway,
  onRetake,
  onSendAnyway,
}: {
  trip: DriverTrip;
  photo: File;
  problem: PhotoProblem;
  canSendAnyway: boolean;
  onRetake: () => void;
  onSendAnyway: () => void;
}) {
  const photoUrl = useMemo(() => URL.createObjectURL(photo), [photo]);
  const replay = useVoicePrompt(problem); // "blurred" and "dark" are prompts of their own.

  return (
    <main className="driver-check">
      <div className="cam-top">
        <span className="fig">{trip.trip_code}</span>
        <span>{trip.destination}</span>
      </div>
      <img className="driver-check__photo" src={photoUrl} alt="The photo you just took" />
      <section className="driver-check__sheet">
        <div className="retake__head">
          <span className="ico retake__icon">
            <svg
              width="26"
              height="26"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M20 12a8 8 0 11-3-6.2M20 4v5h-5" />
            </svg>
          </span>
          <div className="retake__words">
            <h1>फिर से फोटो लें</h1>
            <p className="muted">{PROBLEM_TEXT[problem]}</p>
          </div>
          <SpeakerButton onPlay={replay} />
        </div>
        <button className="btn btn--ink big retake__button" type="button" onClick={onRetake}>
          फिर से फोटो, Retake
        </button>
        {canSendAnyway && (
          <button className="btn btn--card big retake__button" type="button" onClick={onSendAnyway}>
            यही भेजें, Send anyway
          </button>
        )}
      </section>
    </main>
  );
}
