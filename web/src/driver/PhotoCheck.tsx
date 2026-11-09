import { useEffect, useRef, useState } from "react";

import { getAttempt, type AttemptResult, type DriverTrip } from "../lib/api";
import type { PendingPhoto } from "./pendingPhotos";
import { photoQueue } from "./photoQueue";
import { useVoicePrompt } from "./useVoice";

const POLL_EVERY_MS = 2_000;
const GIVE_UP_AFTER_MS = 30_000; // The driver isn't kept at the gate after this. The check goes on.

export type CheckEnd =
  | { name: "result"; attempt: AttemptResult }
  | { name: "gave-up" }
  | { name: "saved" } // No network: the photo is safe on the phone and will send itself.
  | { name: "refused" } // The server said no. The photo is still on the phone.
  | { name: "link-dead" };

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollUntilDone(token: string, attempt: AttemptResult): Promise<CheckEnd> {
  const deadline = Date.now() + GIVE_UP_AFTER_MS;
  let latest = attempt;
  while (latest.outcome === null) {
    if (Date.now() >= deadline) return { name: "gave-up" };
    await wait(POLL_EVERY_MS);
    try {
      latest = await getAttempt(token, attempt.attempt_id);
    } catch {
      // One failed poll on a weak network isn't an answer. The deadline ends this.
    }
  }
  return { name: "result", attempt: latest };
}

async function sendAndCheck(
  photo: PendingPhoto,
  alreadySent: AttemptResult | null,
  onSent: () => void,
): Promise<CheckEnd> {
  if (alreadySent) return pollUntilDone(photo.token, alreadySent);

  const outcome = await photoQueue.trySend(photo.tripCode);
  switch (outcome.status) {
    case "sent":
      onSent();
      return pollUntilDone(photo.token, outcome.attempt);
    case "link-dead":
      return { name: "link-dead" };
    case "refused":
      return { name: "refused" };
    case "waiting":
    case "nothing-pending":
      return { name: "saved" };
  }
}

function sizeLabel(bytes: number): string {
  return bytes >= 1_000_000
    ? `${(bytes / 1_000_000).toFixed(1)} MB`
    : `${Math.round(bytes / 1000)} KB`;
}

function Step({ done, title, detail }: { done: boolean; title: string; detail: string }) {
  return (
    <div className="step">
      <span className={done ? "ico driver__step-done" : "ico driver__step-busy"}>
        {done && (
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M5 12l5 5 9-10" />
          </svg>
        )}
      </span>
      <p>
        {title}
        <br />
        <span className="muted driver__step-detail">{detail}</span>
      </p>
    </div>
  );
}

/** Sends one photo, waits for its check and reports how that ended. The screen is Checking.html. */
export default function PhotoCheck({
  trip,
  photo,
  alreadySent,
  onEnd,
}: {
  trip: DriverTrip;
  photo: PendingPhoto;
  alreadySent: AttemptResult | null; // Set when the photo went up from the Offline screen.
  onEnd: (end: CheckEnd) => void;
}) {
  const [preview, setPreview] = useState<string | null>(null);
  const [sent, setSent] = useState(alreadySent !== null);
  const started = useRef(false);
  useVoicePrompt("checking"); // No speaker button here, as in Checking.html: it lasts seconds.

  useEffect(() => {
    const url = URL.createObjectURL(photo.blob);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  useEffect(() => {
    if (started.current) return; // StrictMode runs effects twice in development.
    started.current = true;
    void sendAndCheck(photo, alreadySent, () => setSent(true)).then(onEnd);
  }, [photo, alreadySent, onEnd]);

  // A photo already under the limit can come out of compression the same size. Comparing the
  // labels, not the bytes, avoids "176 KB down to 176 KB".
  const before = sizeLabel(photo.originalBytes);
  const after = sizeLabel(photo.blob.size);
  const shrunk = before !== after;

  return (
    <main className="driver-check">
      <div className="cam-top">
        <span className="fig">{trip.trip_code}</span>
        <span>{trip.destination}</span>
      </div>
      {preview && <img className="driver-check__photo" src={preview} alt="Your POD photo" />}
      <section className="driver-check__sheet">
        <div>
          <h1>जाँच हो रही है</h1>
          <p className="muted">Checking the photo. Please stay at the gate.</p>
        </div>
        <Step
          done
          title={photo.deviceCheck === "passed" ? "Sharp and bright enough" : "Sent as it is"}
          detail="Checked on the phone, no network needed"
        />
        <Step
          done={sent}
          title={shrunk ? "Made smaller and sent" : "Sent"}
          detail={
            shrunk ? `${before} down to ${after}` : `${after}, already small enough to send`
          }
        />
        {sent && (
          <Step
            done={false}
            title="Reading LR, stamp, quantity, remarks, date and signature"
            detail="About five seconds"
          />
        )}
      </section>
    </main>
  );
}
