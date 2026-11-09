import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router";

import {
  ApiError,
  createExport,
  exportFileUrl,
  getBillingQueue,
  getExports,
  type BillingClient,
  type BillingCycle,
  type BillingQueue,
  type ExportSummary,
} from "../lib/api";
import { rupees } from "../lib/format";
import { ErrorState, Skeleton, type Loadable } from "./LoadStates";
import { useSession } from "./session";

type Page = { queue: BillingQueue; exports: ExportSummary[] };

function clientTotal(client: BillingClient): number {
  return client.trips.reduce((total, trip) => total + trip.freight_paise, 0);
}

function count(amount: number, one: string): string {
  return `${amount} ${one}${amount === 1 ? "" : "s"}`;
}

function dayOf(iso: string): number {
  return Number(iso.slice(8));
}

/** "1 to 15 Nov". The dates are calendar dates, so UTC keeps the month from shifting. */
function cycleLabel(cycle: BillingCycle): string {
  const month = new Intl.DateTimeFormat("en-IN", { month: "short", timeZone: "UTC" }).format(
    new Date(`${cycle.start}T00:00:00Z`),
  );
  return `${dayOf(cycle.start)} to ${dayOf(cycle.end)} ${month}`;
}

function exportedTime(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  }).format(new Date(iso));
}

function ClientRows({
  client,
  selected,
  onToggle,
}: {
  client: BillingClient;
  selected: Set<string>;
  onToggle: (tripIds: string[], on: boolean) => void;
}) {
  const ids = client.trips.map((trip) => trip.id);
  const chosen = ids.filter((id) => selected.has(id)).length;

  return (
    <>
      <tr className="billing__client">
        <td>
          <input
            type="checkbox"
            aria-label={`Select all for ${client.client_name}`}
            checked={chosen === ids.length}
            ref={(box) => {
              if (box) box.indeterminate = chosen > 0 && chosen < ids.length;
            }}
            onChange={(event) => onToggle(ids, event.target.checked)}
          />
        </td>
        <td colSpan={4}>
          {client.client_name}{" "}
          <span className="muted">{count(client.trips.length, "trip")}</span>
        </td>
        <td className="fig r">{rupees(clientTotal(client))}</td>
      </tr>
      {client.trips.map((trip) => (
        <tr key={trip.id}>
          <td>
            <input
              type="checkbox"
              aria-label={`Select ${trip.trip_code}`}
              checked={selected.has(trip.id)}
              onChange={(event) => onToggle([trip.id], event.target.checked)}
            />
          </td>
          <td className="fig">{trip.trip_code}</td>
          <td>{trip.destination}</td>
          <td className="fig muted">{trip.lr_number}</td>
          <td>
            {/* Billed in full either way: the remark goes in the voucher narration. */}
            {trip.remark ? trip.remark : <span className="settled">Verified</span>}
          </td>
          <td className="fig r">{rupees(trip.freight_paise)}</td>
        </tr>
      ))}
    </>
  );
}

function ExportLinks({ id }: { id: string }) {
  return (
    <>
      <a className="btn btn--card" href={exportFileUrl(id, "xml")} download>
        Download Tally XML
      </a>
      <a className="btn btn--card" href={exportFileUrl(id, "photos")} download>
        Download POD photos
      </a>
    </>
  );
}

export default function Billing() {
  const { setUser } = useSession();
  const [page, setPage] = useState<Loadable<Page>>({ state: "loading" });
  const [cycle, setCycle] = useState<string | null>(null);
  const [clientId, setClientId] = useState("all");
  // Starts empty, unlike the design's sample: an export can't be undone, so each trip is a choice.
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [finished, setFinished] = useState<ExportSummary | null>(null);

  const load = useCallback(async () => {
    setPage({ state: "loading" });
    try {
      const [queue, exports] = await Promise.all([getBillingQueue(cycle), getExports()]);
      setPage({ state: "ready", value: { queue, exports } });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setUser(null);
      else setPage({ state: "error" });
    }
  }, [cycle, setUser]);

  useEffect(() => {
    void load();
  }, [load]);

  const queue = page.state === "ready" ? page.value.queue : null;
  const visible = useMemo(
    () =>
      (queue?.clients ?? []).filter((client) => clientId === "all" || client.client_id === clientId),
    [queue, clientId],
  );
  // Only what can be seen counts, so a client filter can't export a trip off the screen.
  const chosen = visible
    .map((client) => ({
      ...client,
      trips: client.trips.filter((trip) => selected.has(trip.id)),
    }))
    .filter((client) => client.trips.length > 0);
  const chosenTrips = chosen.flatMap((client) => client.trips);
  const total = chosen.reduce((sum, client) => sum + clientTotal(client), 0);

  function chooseCycle(start: string) {
    setCycle(start);
    setClientId("all");
    setSelected(new Set()); // An export covers one cycle.
    setProblem(null);
  }

  function toggle(tripIds: string[], on: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      tripIds.forEach((id) => (on ? next.add(id) : next.delete(id)));
      return next;
    });
  }

  async function exportNow() {
    setExporting(true);
    setProblem(null);
    setFinished(null);
    try {
      setFinished(await createExport(chosenTrips.map((trip) => trip.id)));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setUser(null);
        return;
      }
      // Either the server refused and named the trips, or we don't know how it ended. Reloading
      // below shows the truth in both cases, so the selection can't go stale.
      setProblem(
        error instanceof ApiError && error.detail
          ? error.detail
          : "We couldn't confirm this export. Check Earlier exports before trying again.",
      );
    } finally {
      setExporting(false);
    }
    setSelected(new Set());
    setClientId("all");
    await load();
  }

  return (
    <>
      <div className="head billing__head">
        <h1>Billing</h1>
        {queue && queue.cycles.length > 0 && (
          <div className="groove billing__cycles" role="group" aria-label="Billing cycle">
            {queue.cycles.map((item) => (
              <button
                key={item.start}
                type="button"
                aria-pressed={item.start === queue.cycle_start}
                onClick={() => chooseCycle(item.start)}
              >
                {cycleLabel(item)}
              </button>
            ))}
          </div>
        )}
        {queue && queue.clients.length > 1 && (
          <label className="muted billing__filter">
            Client
            <select value={clientId} onChange={(event) => setClientId(event.target.value)}>
              <option value="all">All clients</option>
              {queue.clients.map((client) => (
                <option key={client.client_id} value={client.client_id}>
                  {client.client_name}
                </option>
              ))}
            </select>
          </label>
        )}
        {queue && queue.in_review > 0 && (
          <Link className="billing__review-link" to="/office/review">
            {queue.in_review === 1
              ? "1 trip is still in review"
              : `${queue.in_review} trips are still in review`}
          </Link>
        )}
      </div>

      {page.state === "loading" && <Skeleton />}
      {page.state === "error" && <ErrorState onRetry={() => void load()} />}
      {page.state === "ready" && (
        <div className="billing">
          {page.value.queue.clients.length === 0 ? (
            <div className="notice">
              <h1>Nothing to bill</h1>
              <p className="muted">Verified PODs land here, grouped by client and cycle.</p>
              <Link className="btn btn--card" to="/office/review">
                Go to review
              </Link>
            </div>
          ) : (
            <div className="scroll">
              <table className="tbl billing__table">
                <thead>
                  <tr>
                    <th aria-label="Select" />
                    <th>Trip</th>
                    <th>Destination</th>
                    <th>LR</th>
                    <th>POD</th>
                    <th className="r">Freight, ₹</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((client) => (
                    <ClientRows
                      key={client.client_id}
                      client={client}
                      selected={selected}
                      onToggle={toggle}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <aside className="billing__panel">
            <p className="muted billing__label">Selected for export</p>
            <p className="billing__total">₹{rupees(total)}</p>
            <p className="billing__summary">
              {chosenTrips.length === 0
                ? "Select trips to export"
                : `${count(chosenTrips.length, "trip")} for ${count(chosen.length, "client")}, each with its POD photo`}
            </p>
            <button
              className="btn btn--ink"
              type="button"
              disabled={exporting || chosenTrips.length === 0}
              onClick={() => void exportNow()}
            >
              {exporting ? "Exporting…" : "Export to Tally"}
            </button>
            <p className="muted billing__note">
              Creates draft vouchers in Tally. Nothing goes to a client from here.
            </p>

            {problem && (
              <p className="billing__problem" role="alert">
                {problem}
              </p>
            )}
            {finished && (
              <div className="billing__finished" role="status">
                <p>
                  Exported {count(finished.trip_count, "trip")} for ₹
                  {rupees(finished.total_paise)}.
                </p>
                <ExportLinks id={finished.id} />
              </div>
            )}

            <div className="billing__earlier">
              <p className="billing__earlier-title">Earlier exports</p>
              {page.value.exports.length === 0 && <p className="muted">No exports yet.</p>}
              {page.value.exports.map((item) => (
                <div className="billing__export" key={item.id}>
                  <span className="fig">{exportedTime(item.exported_at)}</span>
                  <span className="fig">{count(item.trip_count, "trip")}</span>
                  <a href={exportFileUrl(item.id, "xml")} download>
                    XML
                  </a>
                  <a href={exportFileUrl(item.id, "photos")} download>
                    Photos
                  </a>
                </div>
              ))}
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
