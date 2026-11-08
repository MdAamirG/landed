import { useEffect, useRef, useState } from "react";

import type { AttemptResult, DriverTrip } from "../lib/api";
import type { PendingPhoto, SendOutcome } from "./pendingPhotos";
import { photoQueue } from "./photoQueue";
import { SpeakerButton, useVoicePrompt } from "./useVoice";

const RETRY_EVERY_MS = 30_000;

function shortTime(moment: Date): string {
  return moment.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  });
}

/** The Offline screen. It keeps trying while it is open, and reports the first answer that isn't
 * "wait". "Saved on the phone" exists only here: on the server the trip stays where it was.
 */
export default function SavedOffline({
  trip,
  photo,
  onTakeNew,
  onSent,
  onStopped,
}: {
  trip: DriverTrip;
  photo: PendingPhoto;
  onTakeNew: () => void;
  onSent: (attempt: AttemptResult) => void;
  onStopped: (outcome: SendOutcome) => void;
}) {
  // This screen only opens after a send has failed, so "now" is right for a first try.
  const [triedAt, setTriedAt] = useState(photo.triedAt ?? new Date());
  const replay = useVoicePrompt("saved_offline");

  // In refs, so a parent re-render doesn't restart the 30-second timer.
  const handlers = useRef({ onSent, onStopped });
  handlers.current = { onSent, onStopped };

  useEffect(() => {
    let closed = false;

    async function retry() {
      const outcome = await photoQueue.trySend(trip.trip_code);
      if (closed) return;
      setTriedAt(new Date());
      if (outcome.status === "sent") handlers.current.onSent(outcome.attempt);
      else if (outcome.status !== "waiting") handlers.current.onStopped(outcome);
    }

    window.addEventListener("online", retry);
    const timer = setInterval(() => void retry(), RETRY_EVERY_MS);
    return () => {
      closed = true;
      window.removeEventListener("online", retry);
      clearInterval(timer);
    };
  }, [trip.trip_code]);

  return (
    <main className="driver driver--centred desk">
      <span className="ico driver__saved-icon">
        <svg
          width="56"
          height="56"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <rect x="7" y="2.5" width="10" height="19" rx="2" />
          <path d="M10.5 18.5h3" />
          <path d="M12 7v6M9.5 10.5L12 13l2.5-2.5" />
        </svg>
      </span>
      <h1 className="driver__saved-title">फोटो फ़ोन में सेव है</h1>
      <p className="muted">Saved on the phone. It sends by itself when the network is back.</p>
      <SpeakerButton onPlay={replay} />

      <section className="stock driver__saved-item">
        <div>
          <p>
            <span className="fig">{trip.trip_code}</span>, {trip.destination}
          </p>
          <p className="muted">
            <span className="fig">{Math.round(photo.blob.size / 1000)} KB</span>, waiting for network
          </p>
        </div>
        <span className="ico driver__step-busy" role="img" aria-label="Waiting to upload" />
      </section>

      {photo.deviceCheck === "passed" && (
        <p className="driver__sent">The phone checked it: sharp and bright enough</p>
      )}
      <p className="muted">If the office needs a new photo, you get an SMS with a link.</p>
      <p className="muted driver__tried">
        Tried at <span className="fig">{shortTime(triedAt)}</span>. Trying again on its own.
      </p>
      <button className="btn btn--card big driver__retry" type="button" onClick={onTakeNew}>
        नई फोटो लें, Take a new photo
      </button>
    </main>
  );
}
