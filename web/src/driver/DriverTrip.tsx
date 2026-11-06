import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router";

import { ApiError, getDriverTrip, type DriverTrip as Trip, type PodStatus } from "../lib/api";

// Only these two statuses wait on the driver. Any other means the photo has been dealt with.
const NEEDS_PHOTO: PodStatus[] = ["awaiting_pod", "retake_requested"];

type Screen =
  | { name: "loading" }
  | { name: "unreachable" }
  | { name: "dead-link" }
  | { name: "trip"; trip: Trip };

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

function TakePhoto({ trip }: { trip: Trip }) {
  return (
    <main className="driver desk">
      <TripCard trip={trip} />
      <button className="btn btn--ink big driver__shoot" type="button">
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

function Done({ trip }: { trip: Trip }) {
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
      <p className="muted">POD received. You can leave.</p>
      <p className="fig muted">
        {trip.trip_code}, {trip.destination}
      </p>
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

export default function DriverTrip() {
  const { token = "" } = useParams();
  const [screen, setScreen] = useState<Screen>({ name: "loading" });

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
    case "trip":
      return NEEDS_PHOTO.includes(screen.trip.pod_status) ? (
        <TakePhoto trip={screen.trip} />
      ) : (
        <Done trip={screen.trip} />
      );
  }
}
