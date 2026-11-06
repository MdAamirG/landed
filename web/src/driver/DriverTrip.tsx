import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { useParams } from "react-router";

import DemoControls from "../demo/DemoControls";
import { samplePhoto } from "../demo/samples";
import {
  ApiError,
  getDriverTrip,
  type AttemptResult,
  type DriverTrip as Trip,
  type PodStatus,
} from "../lib/api";
import {
  compressWithStrip,
  decodePhoto,
  photoMeasurements,
  problemWith,
  stripText,
  type DeviceCheck,
  type GpsFix,
  type PhotoProblem,
} from "./capture";
import type { PendingPhoto, SendOutcome } from "./pendingPhotos";
import PhoneCheckFailed from "./PhoneCheckFailed";
import PhotoCheck, { type CheckEnd } from "./PhotoCheck";
import { photoQueue } from "./photoQueue";
import Retake from "./Retake";
import SavedOffline from "./SavedOffline";
import { useLocationFix } from "./useLocationFix";

// Only these two statuses wait on the driver. Any other means the photo has been dealt with.
const NEEDS_PHOTO: PodStatus[] = ["awaiting_pod", "retake_requested"];

type Screen =
  | { name: "loading" }
  | { name: "unreachable" }
  | { name: "dead-link" }
  | { name: "trip"; trip: Trip; notice?: string }
  | { name: "preparing"; trip: Trip }
  | { name: "phone-check-failed"; trip: Trip; shot: Shot; problem: PhotoProblem }
  | { name: "checking"; trip: Trip; photo: PendingPhoto; alreadySent: AttemptResult | null }
  | { name: "saved"; trip: Trip; photo: PendingPhoto }
  | { name: "done"; trip: Trip; message: DoneMessage };

/** A photo as the camera gave it, and the moment it was taken. */
type Shot = { file: File; capturedAt: Date };

const SEND_ANYWAY_AFTER_FAILURES = 2;
const SAMPLE_GPS_ACCURACY_M = 12; // A sample has no real fix, so it claims a phone's usual one.

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

const REFUSED_NOTICE = "The photo didn't send. Please call the office.";

// The last trip this link showed, so reopening it in a dead zone still shows the trip. It holds
// what the driver can already see, so no consignee details. Storage can be refused or cleared,
// and then the app just needs network, as it does on a first visit.
function rememberTrip(token: string, trip: Trip) {
  try {
    localStorage.setItem(`trip:${token}`, JSON.stringify(trip));
  } catch {
    // Nothing to do: this is a convenience.
  }
}

function rememberedTrip(token: string): Trip | null {
  try {
    const stored = localStorage.getItem(`trip:${token}`);
    return stored ? (JSON.parse(stored) as Trip) : null;
  } catch {
    return null;
  }
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

function useOnline(): boolean {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
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
  hasLocation,
  onPhoto,
  onUseSample,
}: {
  trip: Trip;
  notice?: string;
  hasLocation: boolean;
  onPhoto: (photo: File) => void;
  onUseSample: () => void;
}) {
  const camera = useRef<HTMLInputElement>(null);
  const online = useOnline();

  return (
    <main className="driver desk">
      <CameraInput input={camera} onPhoto={onPhoto} />
      <TripCard trip={trip} />
      {notice && (
        <p className="form-error" role="alert">
          {notice}
        </p>
      )}
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
      <DemoControls trip={trip} onUseSample={onUseSample} />
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
      <div className="muted driver__status">
        <p>{hasLocation ? "Location ready" : "Finding location"}</p>
        {!online && <p>No network here. The photo will be saved on the phone.</p>}
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
      <DemoControls trip={trip} />
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
  onUseSample,
}: {
  trip: Trip;
  lastPhoto: Blob | null;
  onPhoto: (photo: File) => void;
  onUseSample: () => void;
}) {
  const camera = useRef<HTMLInputElement>(null);
  const photoUrl = useMemo(() => (lastPhoto ? URL.createObjectURL(lastPhoto) : null), [lastPhoto]);

  return (
    <>
      <CameraInput input={camera} onPhoto={onPhoto} />
      <Retake
        trip={trip}
        photoUrl={photoUrl}
        onRetake={() => camera.current?.click()}
        onUseSample={onUseSample}
      />
    </>
  );
}

export default function DriverTrip() {
  const { token = "" } = useParams();
  const [screen, setScreen] = useState<Screen>({ name: "loading" });
  const [lastPhoto, setLastPhoto] = useState<Blob | null>(null);
  const phoneCheckFailures = useRef(0);
  const retakeCamera = useRef<HTMLInputElement>(null);
  const location = useLocationFix();

  const newCamera = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Only in a build: Vite's dev server would be fighting a worker that caches its files.
    if (import.meta.env.PROD && "serviceWorker" in navigator) {
      void navigator.serviceWorker.register("/sw.js");
    }
  }, []);

  /** The trip from the server, or the remembered one if the server can't be reached. */
  const fetchTrip = useCallback(async (): Promise<Trip | "dead-link" | "unreachable"> => {
    try {
      const trip = await getDriverTrip(token);
      rememberTrip(token, trip);
      return trip;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return "dead-link";
      return rememberedTrip(token) ?? "unreachable";
    }
  }, [token]);

  const load = useCallback(async () => {
    setScreen({ name: "loading" });
    const trip = await fetchTrip();
    if (trip === "dead-link" || trip === "unreachable") {
      setScreen(trip === "dead-link" ? { name: "dead-link" } : { name: "unreachable" });
      return;
    }
    // A photo left from earlier goes first. This is the "on app open" retry.
    const pending = await photoQueue.pending(trip.trip_code);
    setScreen(
      pending
        ? { name: "checking", trip, photo: pending, alreadySent: null }
        : { name: "trip", trip },
    );
  }, [fetchTrip]);

  useEffect(() => {
    void load();
  }, [load]);

  /** Compress and print the strip, then save it before any attempt to send it. */
  const send = useCallback(
    async (
      trip: Trip,
      shot: Shot,
      photo: ImageBitmap,
      deviceCheck: DeviceCheck,
      gps: GpsFix | null = location,
    ) => {
      const text = stripText(trip.trip_code, shot.capturedAt, gps);
      const pending = await photoQueue.save({
        blob: await compressWithStrip(photo, text),
        originalBytes: shot.file.size,
        capturedAt: shot.capturedAt,
        gps,
        deviceCheck,
        tripCode: trip.trip_code,
        token,
      });
      setLastPhoto(pending.blob);
      setScreen({ name: "checking", trip, photo: pending, alreadySent: null });
    },
    [location, token],
  );

  /** The phone check. A failure here needs no network and costs no retake. */
  const handlePhoto = useCallback(
    async (trip: Trip, file: File) => {
      const shot = { file, capturedAt: new Date() };
      setScreen({ name: "preparing", trip });
      try {
        const photo = await decodePhoto(file);
        const problem = problemWith(photoMeasurements(photo));
        if (problem) {
          phoneCheckFailures.current += 1;
          setScreen({ name: "phone-check-failed", trip, shot, problem });
        } else {
          phoneCheckFailures.current = 0;
          await send(trip, shot, photo, "passed");
        }
      } catch {
        setScreen({ name: "trip", trip, notice: "That photo couldn't be read. Please try again." });
      }
    },
    [send],
  );

  const sendAnyway = useCallback(
    async (trip: Trip, shot: Shot) => {
      setScreen({ name: "preparing", trip });
      try {
        await send(trip, shot, await decodePhoto(shot.file), "sent_anyway");
      } catch {
        setScreen({ name: "trip", trip, notice: "That photo couldn't be read. Please try again." });
      }
    },
    [send],
  );

  /** A demo trip's sample, sent with the sheet's date from the gate (see DemoSampleOut). */
  const sendSample = useCallback(
    async (trip: Trip) => {
      const sample = trip.demo_sample;
      if (!sample) return;
      setScreen({ name: "preparing", trip });
      try {
        const file = await samplePhoto(sample.scenario);
        const photo = await decodePhoto(file);
        // No stop at the phone check here: the blurred sample is meant to reach the real AI check.
        const problem = problemWith(photoMeasurements(photo));
        await send(
          trip,
          { file, capturedAt: new Date(sample.captured_at) },
          photo,
          problem ? "sent_anyway" : "passed",
          { lat: sample.gps_lat, lng: sample.gps_lng, accuracyM: SAMPLE_GPS_ACCURACY_M },
        );
      } catch {
        setScreen({ name: "trip", trip, notice: "The sample photo didn't load. Try again." });
      }
    },
    [send],
  );

  /** Sending has ended without a result. In all of these the photo stays on the phone. */
  const stopSending = useCallback(
    (trip: Trip, reason: SendOutcome["status"]) => {
      if (reason === "refused") setScreen({ name: "trip", trip, notice: REFUSED_NOTICE });
      else if (reason === "link-dead") setScreen({ name: "dead-link" });
      else void load(); // The photo has gone, so it was sent some other way. Ask the server.
    },
    [load],
  );

  const finishCheck = useCallback(
    (trip: Trip, photo: PendingPhoto, end: CheckEnd) => {
      if (end.name === "saved") setScreen({ name: "saved", trip, photo });
      else if (end.name === "gave-up") setScreen({ name: "done", trip, message: "sms-later" });
      else if (end.name === "refused") stopSending(trip, "refused");
      else if (end.name === "link-dead") stopSending(trip, "link-dead");
      else if (end.attempt.outcome === "retake_requested") void load();
      else {
        const message = doneMessageFor(end.attempt.outcome ?? "needs_review");
        setScreen({ name: "done", trip, message });
      }
    },
    [load, stopSending],
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
          <button
            className="btn btn--ink big driver__retry"
            type="button"
            onClick={() => void load()}
          >
            फिर से कोशिश करें
          </button>
        </main>
      );
    case "dead-link":
      return <DeadLink />;
    case "trip": {
      const { trip, notice } = screen;
      const onPhoto = (file: File) => void handlePhoto(trip, file);
      const onUseSample = () => void sendSample(trip);
      if (trip.pod_status === "retake_requested" && !notice) {
        return (
          <RetakeScreen
            trip={trip}
            lastPhoto={lastPhoto}
            onPhoto={onPhoto}
            onUseSample={onUseSample}
          />
        );
      }
      return NEEDS_PHOTO.includes(trip.pod_status) ? (
        <TakePhoto
          trip={trip}
          notice={notice}
          hasLocation={location !== null}
          onPhoto={onPhoto}
          onUseSample={onUseSample}
        />
      ) : (
        <Done trip={trip} message={doneMessageFor(trip.pod_status)} />
      );
    }
    case "preparing":
      return (
        <main className="driver driver--centred desk" role="status">
          <p className="muted">Checking the photo…</p>
        </main>
      );
    case "phone-check-failed": {
      const { trip, shot, problem } = screen;
      return (
        <>
          <CameraInput input={retakeCamera} onPhoto={(file) => void handlePhoto(trip, file)} />
          <PhoneCheckFailed
            trip={trip}
            photo={shot.file}
            problem={problem}
            canSendAnyway={phoneCheckFailures.current >= SEND_ANYWAY_AFTER_FAILURES}
            onRetake={() => retakeCamera.current?.click()}
            onSendAnyway={() => void sendAnyway(trip, shot)}
          />
        </>
      );
    }
    case "checking":
      return (
        <PhotoCheck
          trip={screen.trip}
          photo={screen.photo}
          alreadySent={screen.alreadySent}
          onEnd={(end) => finishCheck(screen.trip, screen.photo, end)}
        />
      );
    case "saved": {
      const { trip, photo } = screen;
      return (
        <>
          <CameraInput input={newCamera} onPhoto={(file) => void handlePhoto(trip, file)} />
          <SavedOffline
            trip={trip}
            photo={photo}
            onTakeNew={() => newCamera.current?.click()}
            onSent={(attempt) =>
              setScreen({ name: "checking", trip, photo, alreadySent: attempt })
            }
            onStopped={(outcome) => stopSending(trip, outcome.status)}
          />
        </>
      );
    }
    case "done":
      return <Done trip={screen.trip} message={screen.message} />;
  }
}
