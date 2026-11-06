import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import {
  ApiError,
  approveTrip,
  attemptPhotoUrl,
  getReviewQueue,
  getReviewTrip,
  revealContact,
  saveField,
  type FieldValue,
  type PodFieldName,
  type Quantity,
  type Remarks,
  type ReviewAttempt,
  type ReviewField,
  type ReviewQueueItem,
  type ReviewTrip,
} from "../lib/api";
import { FIELD_LABELS, MIN_CONFIDENCE, REASON_LABELS } from "./reviewLabels";
import { useSession } from "./session";

type Loadable<T> = { state: "loading" } | { state: "error" } | { state: "ready"; value: T };

function indiaTime(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  }).format(new Date(iso));
}

function waitedFor(iso: string): string {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60_000));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `${hours} h` : `${Math.round(hours / 24)} d`;
}

function reasonLabel(code: string | null): string {
  return code ? (REASON_LABELS[code] ?? code) : "Needs a person";
}

function Skeleton() {
  return (
    <div role="status" aria-label="Loading">
      {[0, 1, 2].map((row) => (
        <div className="skeleton-row" key={row}>
          <span style={{ width: "42%" }} />
          <span style={{ width: "68%" }} />
          <span style={{ width: "30%" }} />
        </div>
      ))}
    </div>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="notice" role="alert">
      <h1>We couldn't load this</h1>
      <p className="muted">Check your connection, then try again.</p>
      <button className="btn btn--ink" type="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

function Queue({
  items,
  selected,
  onSelect,
}: {
  items: ReviewQueueItem[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <ol className="review__queue" aria-label="Waiting for review">
      {items.map((item) => (
        <li key={item.id}>
          <button
            type="button"
            aria-current={item.id === selected ? "true" : undefined}
            onClick={() => onSelect(item.id)}
          >
            <span className="review__queue-top">
              <span className="fig">{item.trip_code}</span>
              <span className="muted fig small">{waitedFor(item.waiting_since)}</span>
            </span>
            <span className="muted small">
              {item.destination}, {item.client_name}
              {item.ownership === "hired" ? ", hired" : ""}
            </span>
            <span className="tag">{reasonLabel(item.status_reason)}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}

function Photo({ attempt }: { attempt: ReviewAttempt | null }) {
  const [zoom, setZoom] = useState(1);
  const [turns, setTurns] = useState(0);

  return (
    <figure style={{ margin: 0 }}>
      <div className="review__pane-head">
        <span>The photo</span>
        <div className="review__tools">
          <button
            className="btn btn--card btn--sm"
            type="button"
            aria-label="Zoom out"
            onClick={() => setZoom((value) => Math.max(1, value - 0.5))}
          >
            −
          </button>
          <button
            className="btn btn--card btn--sm"
            type="button"
            aria-label="Zoom in"
            onClick={() => setZoom((value) => Math.min(4, value + 0.5))}
          >
            +
          </button>
          <button
            className="btn btn--card btn--sm"
            type="button"
            aria-label="Rotate"
            onClick={() => setTurns((value) => value + 1)}
          >
            <svg
              width="15"
              height="15"
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
          </button>
        </div>
      </div>
      <div className="review__board">
        {attempt ? (
          <img
            className="review__photo"
            src={attemptPhotoUrl(attempt.id)}
            alt={`POD photo, attempt ${attempt.attempt_no}`}
            // Width rather than scale, so a zoomed photo can be scrolled to all of its edges.
            style={{ width: `${zoom * 100}%`, transform: `rotate(${turns * 90}deg)` }}
          />
        ) : (
          <p>No photo has arrived for this trip.</p>
        )}
      </div>
      {attempt && (
        <figcaption className="muted review__caption">
          Taken <span className="fig">{indiaTime(attempt.captured_at)}</span>
          {attempt.distance_km !== null ? (
            <>
              , <span className="fig">{attempt.distance_km.toFixed(1)} km</span> from the consignee
            </>
          ) : (
            ", no location"
          )}
          . <span className="fig">{Math.round(attempt.size_bytes / 1000)} KB</span>. This photo is
          the record.
          {attempt.late && " This is a late photo. It wasn't checked and changes nothing."}
          {attempt.clock_corrected && " The phone's clock was wrong, so this is the arrival time."}
          {attempt.device_check === "sent_anyway" &&
            " The phone check failed and the driver sent it anyway."}
        </figcaption>
      )}
    </figure>
  );
}

function presenceOptions() {
  return (
    <>
      <option value="" disabled>
        Choose
      </option>
      <option value="present">Present</option>
      <option value="absent">Absent</option>
    </>
  );
}

/** One field's control. It holds its own draft and saves when the executive leaves the field. */
function FieldControl({
  id,
  row,
  disabled,
  flagged,
  onSave,
}: {
  id: string;
  row: ReviewField;
  disabled: boolean;
  flagged: boolean;
  onSave: (value: FieldValue) => void;
}) {
  const inputClass = flagged ? "inp inp--flagged" : "inp";
  const value = disabled ? row.ai_value : row.final_value;

  // Quantity and remarks hold two values, so their draft is an object.
  const [quantity, setQuantity] = useState<Quantity>(
    (row.field === "quantity_received" && (value as Quantity | null)) || {
      number: null,
      unit: null,
    },
  );
  const [remarks, setRemarks] = useState<Remarks>(
    (row.field === "remarks" && (value as Remarks | null)) || { text: "", kind: "none" },
  );
  const [text, setText] = useState(typeof value === "string" ? value : "");

  function commitText() {
    if (text !== (value ?? "")) onSave(text);
  }

  switch (row.field) {
    case "consignee_stamp":
    case "signature":
      return (
        <select
          id={id}
          className={inputClass}
          disabled={disabled}
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            onSave(event.target.value);
          }}
        >
          {presenceOptions()}
        </select>
      );
    case "quantity_received": {
      const commit = () => {
        if (quantity.number !== null && quantity.unit) onSave(quantity);
      };
      return (
        <div className="review__control">
          <input
            id={id}
            className={inputClass}
            type="number"
            min="0"
            step="any"
            disabled={disabled}
            value={quantity.number ?? ""}
            onChange={(event) =>
              setQuantity({
                ...quantity,
                number: event.target.value === "" ? null : Number(event.target.value),
              })
            }
            onBlur={commit}
          />
          <input
            className={inputClass}
            aria-label="Unit"
            disabled={disabled}
            value={quantity.unit ?? ""}
            onChange={(event) => setQuantity({ ...quantity, unit: event.target.value })}
            onBlur={commit}
          />
        </div>
      );
    }
    case "remarks":
      return (
        <div className="review__control">
          <input
            id={id}
            className={inputClass}
            disabled={disabled}
            value={remarks.text ?? ""}
            onChange={(event) => setRemarks({ ...remarks, text: event.target.value })}
            onBlur={() => onSave({ ...remarks, text: remarks.text ?? "" })}
          />
          <select
            className={inputClass}
            aria-label="Kind of remark"
            disabled={disabled}
            value={remarks.kind}
            onChange={(event) => {
              const next = { text: remarks.text ?? "", kind: event.target.value };
              setRemarks(next);
              onSave(next);
            }}
          >
            <option value="none">None</option>
            <option value="shortage">Shortage</option>
            <option value="damage">Damage</option>
            <option value="other">Other</option>
          </select>
        </div>
      );
    case "delivery_date":
      return (
        <input
          id={id}
          className={inputClass}
          type="date"
          disabled={disabled}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onBlur={() => text && commitText()}
        />
      );
    default:
      return (
        <input
          id={id}
          className={inputClass}
          disabled={disabled}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onBlur={() => text && commitText()}
        />
      );
  }
}

function confidenceWord(confidence: number | null): string {
  if (confidence === null) return "blank";
  return confidence < MIN_CONFIDENCE ? "check" : "high";
}

function describe(value: FieldValue): string {
  if (value === null) return "nothing";
  if (typeof value === "string") return value;
  if ("number" in value) return `${value.number ?? "?"} ${value.unit ?? ""}`.trim();
  return value.text ? `${value.text} (${value.kind})` : `no remark (${value.kind})`;
}

const FLAGGED_BY: Partial<Record<PodFieldName, string[]>> = {
  lr_number: ["lr_mismatch", "lr_missing"],
  quantity_received: ["qty_short", "qty_mismatch", "quantity_missing"],
  remarks: ["shortage_remark", "damage_remark", "other_remark"],
  delivery_date: ["date_mismatch", "date_missing"],
  consignee_stamp: ["stamp_missing"],
  signature: ["signature_missing"],
};

function FieldRow({
  trip,
  row,
  editable,
  codes,
  onSave,
}: {
  trip: ReviewTrip;
  row: ReviewField;
  editable: boolean;
  codes: string[];
  onSave: (field: PodFieldName, value: FieldValue) => void;
}) {
  const word = confidenceWord(row.ai_confidence);
  const id = `field-${row.field}`;
  const flagged = (FLAGGED_BY[row.field] ?? []).some((code) => codes.includes(code));
  const label =
    row.field === "quantity_received"
      ? `Quantity received, of ${trip.qty_dispatched} sent`
      : FIELD_LABELS[row.field];

  return (
    <div className="review__row">
      <label htmlFor={id}>{label}</label>
      <FieldControl
        id={id}
        row={row}
        disabled={!editable}
        flagged={flagged}
        onSave={(value) => onSave(row.field, value)}
      />
      <span
        className={
          word === "high"
            ? "review__confidence"
            : "review__confidence review__confidence--check"
        }
      >
        {word}
      </span>
      {row.edited && (
        <span className="review__ai-said">The AI read: {describe(row.ai_value)}</span>
      )}
    </div>
  );
}

function Contact({ trip }: { trip: ReviewTrip }) {
  const [revealed, setRevealed] = useState<{ name: string; phone: string } | null>(null);
  const [failed, setFailed] = useState(false);

  async function reveal() {
    setFailed(false);
    try {
      setRevealed(await revealContact(trip.id));
    } catch {
      setFailed(true);
    }
  }

  return (
    <div className="review__block">
      <div className="review__contact">
        <p>
          <span className="muted small">Consignee contact</span>
          <br />
          {revealed?.name ?? trip.consignee_name},{" "}
          <span className="fig">{revealed?.phone ?? trip.consignee_phone}</span>
        </p>
        {!revealed && (
          <button className="btn btn--card btn--sm" type="button" onClick={() => void reveal()}>
            Reveal
          </button>
        )}
      </div>
      {failed && (
        <p className="form-error" role="alert">
          The contact couldn't be revealed. Try again.
        </p>
      )}
    </div>
  );
}

function approveLabel(trip: ReviewTrip, attempt: ReviewAttempt | null): string {
  const remark = attempt?.fields.find((row) => row.field === "remarks")?.final_value as
    | Remarks
    | null
    | undefined;
  if (remark?.kind === "shortage") return "Approve with shortage";
  if (remark?.kind === "damage") return "Approve with damage";
  return trip.pod_status === "disputed" ? "Resolve and approve" : "Approve";
}

/** One trip at the desk. Keyed by trip, so nothing from the last trip carries over. */
function Desk({
  tripId,
  onDone,
  onSignedOut,
}: {
  tripId: string;
  onDone: () => void;
  onSignedOut: () => void;
}) {
  const [loaded, setLoaded] = useState<Loadable<ReviewTrip>>({ state: "loading" });
  const [viewing, setViewing] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [generation, setGeneration] = useState(0); // Up by one each time drafts must reset.

  // Changes go one at a time, each with the version the last one returned. Clicking Approve right
  // after typing saves the field on blur first, and Approve must not then look like a conflict.
  const version = useRef(0);
  const changes = useRef<Promise<unknown>>(Promise.resolve());

  const load = useCallback(async () => {
    setLoaded({ state: "loading" });
    try {
      const trip = await getReviewTrip(tripId);
      version.current = trip.version;
      setLoaded({ state: "ready", value: trip });
      setGeneration((value) => value + 1);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) onSignedOut();
      else setLoaded({ state: "error" });
    }
  }, [tripId, onSignedOut]);

  useEffect(() => {
    void load();
  }, [load]);

  async function applyChange(change: (version: number) => Promise<ReviewTrip>) {
    try {
      const trip = await change(version.current);
      version.current = trip.version;
      setLoaded({ state: "ready", value: trip });
      setNotice(null);
      return trip;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) onSignedOut();
      else if (error instanceof ApiError && error.status === 409) {
        await load();
        setNotice("Someone else saved this trip first. It has been reloaded, so check it again.");
      } else if (error instanceof ApiError && error.status === 422) {
        setNotice("That can't be saved. Check the value and fill in every field.");
      } else setNotice("That didn't save. Check your connection and try again.");
      return null;
    }
  }

  function queueChange(change: (version: number) => Promise<ReviewTrip>) {
    const result = changes.current.then(() => applyChange(change));
    changes.current = result;
    return result;
  }

  async function approveNow(tripId: string) {
    setApproving(true);
    const approved = await queueChange((current) => approveTrip(tripId, current));
    setApproving(false);
    if (approved) onDone();
  }

  if (loaded.state === "loading") return <Skeleton />;
  if (loaded.state === "error") return <ErrorState onRetry={() => void load()} />;

  const trip = loaded.value;
  const current = trip.attempts.find((attempt) => attempt.id === trip.current_attempt_id) ?? null;
  const attempt = trip.attempts.find((row) => row.id === viewing) ?? current;
  const editable = attempt !== null && attempt.id === trip.current_attempt_id && !attempt.late;

  return (
    <>
      <Photo key={attempt?.id ?? "none"} attempt={attempt} />
      <section className="review__fields" aria-label="What the AI read">
        <div className="review__pane-head">
          <h2>What the AI read</h2>
          {attempt?.ai_latency_ms != null && (
            <span className="muted fig small">{(attempt.ai_latency_ms / 1000).toFixed(1)} s</span>
          )}
        </div>
        <p className="muted small">
          {trip.trip_code}, {trip.origin} to {trip.destination}. LR{" "}
          <span className="fig">{trip.lr_number}</span>.
        </p>

        {trip.attempts.length > 1 && (
          <div className="groove" role="group" aria-label="Attempts">
            {trip.attempts.map((row) => (
              <button
                key={row.id}
                type="button"
                aria-pressed={row.id === attempt?.id}
                onClick={() => setViewing(row.id)}
              >
                {row.late ? `Late ${row.attempt_no}` : `Try ${row.attempt_no}`}
              </button>
            ))}
          </div>
        )}

        <div className="review__reasons">
          {(attempt?.reason_codes ?? []).map((code) => (
            <span className="tag" key={code}>
              {reasonLabel(code)}
            </span>
          ))}
        </div>

        {attempt?.fields.map((row) => (
          <FieldRow
            key={`${attempt.id}-${row.field}-${generation}`}
            trip={trip}
            row={row}
            editable={editable}
            codes={attempt.reason_codes}
            onSave={(field, value) =>
              void queueChange((current) => saveField(trip.id, field, value, current))
            }
          />
        ))}

        <div className="review__block">
          {trip.checks.map((check) => (
            <p
              className={check.ok ? "review__check" : "review__check review__check--bad"}
              key={check.label}
            >
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.6"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d={check.ok ? "M5 12l5 5 9-10" : "M6 6l12 12M18 6L6 18"} />
              </svg>
              {check.label}
            </p>
          ))}
        </div>

        <Contact key={trip.id} trip={trip} />

        {notice && (
          <p className="form-error review__note" role="alert">
            {notice}
          </p>
        )}

        <div className="review__actions">
          <button
            className="btn btn--ink"
            type="button"
            disabled={approving || current === null}
            onClick={() => void approveNow(trip.id)}
          >
            {approving ? "Saving…" : approveLabel(trip, current)}
          </button>
        </div>
        <p className="muted review__note">
          Edits and reveals are logged. Approving sends the trip to billing, never an invoice to the
          client.
        </p>
      </section>
    </>
  );
}

export default function Review() {
  const { setUser } = useSession();
  const [queue, setQueue] = useState<Loadable<ReviewQueueItem[]>>({ state: "loading" });
  const [selected, setSelected] = useState<string | null>(null);

  const signedOut = useCallback(() => setUser(null), [setUser]);

  const loadQueue = useCallback(async () => {
    setQueue({ state: "loading" });
    try {
      const items = await getReviewQueue();
      setQueue({ state: "ready", value: items });
      // Keep the current trip if it is still waiting, otherwise move to the oldest.
      setSelected((current) =>
        items.some((item) => item.id === current) ? current : (items[0]?.id ?? null),
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) signedOut();
      else setQueue({ state: "error" });
    }
  }, [signedOut]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const items = queue.state === "ready" ? queue.value : [];

  return (
    <>
      <div className="head">
        <h1>Review</h1>
        {queue.state === "ready" && items.length > 0 && (
          <p className="muted">
            {items.length === 1 ? "One POD needs" : `${items.length} PODs need`} a person. The
            oldest came in {waitedFor(items[0].waiting_since)} ago.
          </p>
        )}
      </div>
      {queue.state === "loading" && <Skeleton />}
      {queue.state === "error" && <ErrorState onRetry={() => void loadQueue()} />}
      {queue.state === "ready" && items.length === 0 && (
        <div className="notice">
          <h1>Nothing to review</h1>
          <p className="muted">PODs with a shortage, damage or an unsure read land here.</p>
          <Link className="btn btn--card" to="/office/billing">
            Go to billing
          </Link>
        </div>
      )}
      {queue.state === "ready" && items.length > 0 && (
        <div className="review">
          <Queue items={items} selected={selected} onSelect={setSelected} />
          {selected && (
            <Desk
              key={selected}
              tripId={selected}
              onDone={() => void loadQueue()}
              onSignedOut={signedOut}
            />
          )}
        </div>
      )}
    </>
  );
}
