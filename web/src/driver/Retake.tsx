import type { DriverTrip } from "../lib/api";

const MAX_RETAKES = 2;

const PHOTO_PROBLEMS = ["photo_blurred", "photo_dark"];

const REASON_TEXT: Record<string, string> = {
  photo_blurred: "The photo is blurred",
  photo_dark: "The photo is too dark",
  stamp_missing: "The stamp is not visible",
  signature_missing: "The signature is not visible",
  lr_missing: "The LR number is not visible",
  quantity_missing: "The quantity is not visible",
  date_missing: "The date is not visible",
};

// The six field checks, and the reason code that fails each one. Remarks has none, because a
// remark can't be fixed by a new photo.
const FIELD_CHECKS = [
  { label: "LR no.", failedBy: "lr_missing" },
  { label: "Stamp", failedBy: "stamp_missing" },
  { label: "Quantity", failedBy: "quantity_missing" },
  { label: "Remarks", failedBy: null },
  { label: "Date", failedBy: "date_missing" },
  { label: "Signature", failedBy: "signature_missing" },
];

function FieldCheck({ label, failed }: { label: string; failed: boolean }) {
  return (
    <div className={failed ? "field-check field-check--failed" : "field-check"}>
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
        <path d={failed ? "M6 6l12 12M18 6L6 18" : "M5 12l5 5 9-10"} />
      </svg>
      <span>{label}</span>
      <span className="visually-hidden">{failed ? "not found" : "found"}</span>
    </div>
  );
}

/** The retake screen, from Retake.html. photoUrl is empty if the driver has reopened the link. */
export default function Retake({
  trip,
  photoUrl,
  onRetake,
}: {
  trip: DriverTrip;
  photoUrl: string | null;
  onRetake: () => void;
}) {
  const reason = trip.reason_codes.find((code) => code in REASON_TEXT);
  // A blurred or dark photo can't vouch for anything on it, so no field gets a tick.
  const photoIsBad = trip.reason_codes.some((code) => PHOTO_PROBLEMS.includes(code));

  return (
    <main className="driver-check">
      <div className="cam-top">
        <span className="fig">{trip.trip_code}</span>
        <span>{trip.destination}</span>
      </div>
      {photoUrl && <img className="driver-check__photo" src={photoUrl} alt="Your last photo" />}
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
          <div>
            <h1>फिर से फोटो लें</h1>
            <p className="muted">{reason ? REASON_TEXT[reason] : "Please take the photo again"}</p>
          </div>
        </div>
        <div className="field-checks">
          {FIELD_CHECKS.map(({ label, failedBy }) => (
            <FieldCheck
              key={label}
              label={label}
              failed={failedBy !== null && (photoIsBad || trip.reason_codes.includes(failedBy))}
            />
          ))}
        </div>
        <button className="btn btn--ink big retake__button" type="button" onClick={onRetake}>
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
            <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
            <circle cx="12" cy="13" r="3.5" />
          </svg>
          फिर से फोटो, Retake
        </button>
        <p className="muted retake__count">
          Retake {trip.retakes_used} of {MAX_RETAKES}. After two, the office checks the photo.
        </p>
      </section>
    </main>
  );
}
