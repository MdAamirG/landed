import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  getAttempt,
  uploadAttempt,
  type AttemptResult,
  type DriverTrip,
} from "../lib/api";

const POLL_EVERY_MS = 2_000;
const GIVE_UP_AFTER_MS = 30_000; // The driver isn't kept at the gate after this. The check goes on.

export type CheckEnd =
  | { name: "result"; attempt: AttemptResult }
  | { name: "gave-up" }
  | { name: "refused" } // The upload itself was refused or never got through.
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

async function sendAndCheck(token: string, photo: File, attemptId: string): Promise<CheckEnd> {
  try {
    const attempt = await uploadAttempt(token, attemptId, photo, new Date());
    return await pollUntilDone(token, attempt);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return { name: "link-dead" };
    return { name: "refused" };
  }
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
  token,
  photo,
  onEnd,
}: {
  trip: DriverTrip;
  token: string;
  photo: File;
  onEnd: (end: CheckEnd) => void;
}) {
  const [preview, setPreview] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    const url = URL.createObjectURL(photo);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  useEffect(() => {
    if (started.current) return; // StrictMode runs effects twice in development.
    started.current = true;
    void sendAndCheck(token, photo, crypto.randomUUID()).then(onEnd);
  }, [token, photo, onEnd]);

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
        <Step done title="Photo sent" detail={`${Math.round(photo.size / 1000)} KB`} />
        <Step
          done={false}
          title="Reading LR, stamp, quantity, remarks, date and signature"
          detail="About five seconds"
        />
      </section>
    </main>
  );
}
