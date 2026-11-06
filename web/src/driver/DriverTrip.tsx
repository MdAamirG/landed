import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { useParams } from "react-router";

import { ApiError, getDriverTrip, type DriverTrip as Trip, type PodStatus } from "../lib/api";
import PhotoCheck, { type CheckEnd } from "./PhotoCheck";
import Retake from "./Retake";

// Only these two statuses wait on the driver. Any other means the photo has been dealt with.
const NEEDS_PHOTO: PodStatus[] = ["awaiting_pod", "retake_requested"];

type Screen =
  | { name: "loading" }
  | { name: "unreachable" }
  | { name: "dead-link" }
  | { name: "trip"; trip: Trip; notice?: string }
  | { name: "checking"; trip: Trip; photo: File }
  | { name: "done"; trip: Trip; message: DoneMessage };

type DoneMessage = "verified" | "with-office" | "sms-later";

const DONE_MESSAGES: Record<DoneMessage, { line: string; sent?: string }> = {
  verified: { line: "POD verified. You can leave.", sent: "Sent to billing" },
  "with-office": { line: "You can leave.", sent: "Sent to office" },
  "sms-later": { line: "You can go, we'll SMS if needed." },
};

function doneMessageFor(status: PodStatus): DoneMessage {
  if (status === "verified" || status === "invoiced") return "verified";
  // Still in checking means the driver left mid-check and has come back.
  return status === "checking" ? "sms-later" : "with-office";
}

/** 341099217735 becomes 3410 9921 7735, the way it is printed on the bill. */
function formatEwayBill(number: string): string {
  return number.replace(/(\d{4})(?=\d)/g, "$1 ");
}

function TripCard({ trip }: { trip: Trip }) {
  return (
    <section className="stock driver__trip" aria-label="Trip">
      <div className="driver__trip-top">
        <span className="fig muted">{trip.trip_code}</span>
        <span className="fig plate">{trip.registration_no}</span>
      </div>
      <h1>
        {trip.origin} to {trip.destination}
      </h1>
      <p className="muted driver__client">{trip.client_name}</p>
      <dl className="dl">
        <div>
          <dt>LR number</dt>
          <dd>{trip.lr_number}</dd>
        </div>
        <div>
          <dt>E-way bill</dt>
          <dd>{formatEwayBill(trip.eway_bill_no)}</dd>
        </div>
      </dl>
    </section>
  );
}

function CameraInput({
  input,
  onPhoto,
}: {
  input: RefObject<HTMLInputElement | null>;
  onPhoto: (photo: File) => void;
}) {
  // capture opens the rear camera straight away on a phone, with nothing to choose.
  return (
    <input
      ref={input}
      className="driver__camera"
      type="file"
      accept="image/*"
      capture="environment"
      aria-label="Take POD photo"
      onChange={(event) => {
        const photo = event.target.files?.[0];
        event.target.value = ""; // So the same file can be picked again after a failure.
        if (photo) onPhoto(photo);
      }}
    />
  );
}

function TakePhoto({
  trip,
  notice,
  onPhoto,
}: {
  trip: Trip;
  notice?: string;
  onPhoto: (photo: File) => void;
}) {
  const camera = useRef<HTMLInputElement>(null);

  return (
    <main className="driver desk">
      <TripCard trip={trip} />
      {notice && (
        <p className="form-error" role="alert">
          {notice}
        </p>
      )}
      <CameraInput input={camera} onPhoto={onPhoto} />
      <button
        className="btn btn--ink big driver__shoot"
        type="button"
        onClick={() => camera.current?.click()}
      >
        <svg
          width="52"
          height="52"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
          <circle cx="12" cy="13" r="3.5" />
        </svg>
        <span className="driver__shoot-hi">फोटो लें</span>
        <span className="driver__shoot-en">Take POD photo</span>
      </button>
      <div className="driver__hint">
        <svg
          width="30"
          height="30"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <rect x="5" y="3" width="14" height="18" rx="2" />
          <path d="M9 8h6M9 12h6M9 16h3" />
        </svg>
        <p>
          रसीद, मोहर और साइन एक फोटो में
          <br />
          <span className="muted">Receipt, stamp and signature in one photo</span>
        </p>
      </div>
    </main>
  );
}

function Done({ trip, message }: { trip: Trip; message: DoneMessage }) {
  const { line, sent } = DONE_MESSAGES[message];
  return (
    <main className="driver driver--centred desk">
      <div className="driver__tick">
        <div>
          <svg
            width="54"
            height="54"
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
        </div>
      </div>
      <h1 className="driver__title">हो गया</h1>
      <p className="muted">{line}</p>
      <p className="fig muted">
        {trip.trip_code}, {trip.destination}
      </p>
      {sent && <p className="driver__sent">{sent}</p>}
    </main>
  );
}

function DeadLink() {
  return (
    <main className="driver driver--centred desk" role="alert">
      <svg
        className="driver__warn"
        width="64"
        height="64"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A15 15 0 013 6a2 2 0 012-2z" />
      </svg>
      <h1 className="driver__title">ऑफिस को फोन करें</h1>
      <p className="muted">This link has stopped working. Call the office for a new one.</p>
    </main>
  );
}

function RetakeScreen({
  trip,
  lastPhoto,
  onPhoto,
}: {
  trip: Trip;
  lastPhoto: File | null;
  onPhoto: (photo: File) => void;
}) {
  const camera = useRef<HTMLInputElement>(null);
  const photoUrl = useMemo(() => (lastPhoto ? URL.createObjectURL(lastPhoto) : null), [lastPhoto]);

  return (
    <>
      <CameraInput input={camera} onPhoto={onPhoto} />
      <Retake trip={trip} photoUrl={photoUrl} onRetake={() => camera.current?.click()} />
    </>
  );
}

export default function DriverTrip() {
  const { token = "" } = useParams();
  const [screen, setScreen] = useState<Screen>({ name: "loading" });
  const [lastPhoto, setLastPhoto] = useState<File | null>(null);

  const load = useCallback(() => {
    setScreen({ name: "loading" });
    getDriverTrip(token)
      .then((trip) => setScreen({ name: "trip", trip }))
      .catch((error) => {
        const linkRefused = error instanceof ApiError && error.status === 401;
        setScreen(linkRefused ? { name: "dead-link" } : { name: "unreachable" });
      });
  }, [token]);

  useEffect(load, [load]);

  const finishCheck = useCallback(
    (trip: Trip, end: CheckEnd) => {
      if (end.name === "link-dead") setScreen({ name: "dead-link" });
      else if (end.name === "gave-up") setScreen({ name: "done", trip, message: "sms-later" });
      else if (end.name === "refused") {
        setScreen({ name: "trip", trip, notice: "The photo didn't send. Please try again." });
      } else if (end.attempt.outcome === "retake_requested") load();
      else {
        const message = doneMessageFor(end.attempt.outcome ?? "needs_review");
        setScreen({ name: "done", trip, message });
      }
    },
    [load],
  );

  switch (screen.name) {
    case "loading":
      return (
        <main className="driver desk" role="status" aria-label="Loading your trip">
          <section className="stock driver__trip driver__trip--loading">
            <span className="line" />
            <span className="line" />
            <span className="line" />
          </section>
        </main>
      );
    case "unreachable":
      return (
        <main className="driver driver--centred desk" role="alert">
          <h1 className="driver__title">नेटवर्क नहीं है</h1>
          <p className="muted">We couldn't reach the office. Try again when you have signal.</p>
          <button className="btn btn--ink big driver__retry" type="button" onClick={load}>
            फिर से कोशिश करें
          </button>
        </main>
      );
    case "dead-link":
      return <DeadLink />;
    case "trip": {
      const { trip, notice } = screen;
      const startCheck = (photo: File) => {
        setLastPhoto(photo);
        setScreen({ name: "checking", trip, photo });
      };
      if (trip.pod_status === "retake_requested" && !notice) {
        return <RetakeScreen trip={trip} lastPhoto={lastPhoto} onPhoto={startCheck} />;
      }
      return NEEDS_PHOTO.includes(trip.pod_status) ? (
        <TakePhoto trip={trip} notice={notice} onPhoto={startCheck} />
      ) : (
        <Done trip={trip} message={doneMessageFor(trip.pod_status)} />
      );
    }
    case "checking":
      return (
        <PhotoCheck
          trip={screen.trip}
          token={token}
          photo={screen.photo}
          onEnd={(end) => finishCheck(screen.trip, end)}
        />
      );
    case "done":
      return <Done trip={screen.trip} message={screen.message} />;
  }
}
