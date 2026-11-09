import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  getDashboard,
  resendDriverLink,
  type BranchDays,
  type Dashboard,
  type MissingPod,
} from "../lib/api";
import ClientLinkPanel from "./ClientLinkPanel";
import { ErrorState, Skeleton, type Loadable } from "./LoadStates";
import MockSmsToast from "./MockSmsToast";
import { useSession } from "./session";

// The brief's success targets and starting points, shown beside each figure.
const TARGET_INVOICE_DAYS = 4;
const SCALE_MINIMUM_DAYS = TARGET_INVOICE_DAYS * 2; // Keeps the target line near the middle.
const DAYS_FROM_HOURS = 72; // Past three days, a count of hours stops being easy to read.

function shown(value: number | null, format: (value: number) => string): string {
  return value === null ? "None yet" : format(value);
}

function sinceDelivery(hours: number): string {
  return hours < DAYS_FROM_HOURS ? `${hours} h` : `${Math.floor(hours / 24)} d`;
}

function Figure({ value, label, note }: { value: string; label: string; note: string }) {
  return (
    <div className="dashboard__figure">
      <dd className="fig dashboard__value">{value}</dd>
      <dt className="dashboard__label">{label}</dt>
      <dd className="muted dashboard__note">{note}</dd>
    </div>
  );
}

function Figures({ dashboard }: { dashboard: Dashboard }) {
  const over24Hours = dashboard.missing.filter((row) => row.over_24_hours).length;
  return (
    <dl className="dashboard__figures">
      <Figure
        value={String(dashboard.missing.length)}
        label="Delivered without a POD"
        note={`${over24Hours} of them over 24 hours`}
      />
      <Figure
        value={shown(dashboard.within_24_hours_percent, (value) => `${Math.round(value)}%`)}
        label="PODs in within 24 hours"
        note="Target 80%"
      />
      <Figure
        value={shown(dashboard.pod_to_invoice_days, (value) => `${value.toFixed(1)} d`)}
        label="POD to invoice, median"
        note={`Target ${TARGET_INVOICE_DAYS} days, was 18`}
      />
      <Figure
        value={shown(dashboard.lost_or_disputed_percent, (value) => `${value.toFixed(1)}%`)}
        label="PODs lost or disputed"
        note="Target 0.5%, was 1.5%"
      />
    </dl>
  );
}

type Resend =
  | { state: "idle" | "sending" }
  | { state: "sent"; to: string; token: string | null }
  | { state: "failed"; why: string };

function ResendLink({ tripId, onSignedOut }: { tripId: string; onSignedOut: () => void }) {
  const [resend, setResend] = useState<Resend>({ state: "idle" });

  async function send() {
    setResend({ state: "sending" });
    try {
      const { sent_to: to, driver_token: token } = await resendDriverLink(tripId);
      setResend({ state: "sent", to, token });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        onSignedOut();
      } else if (error instanceof ApiError && error.status === 409) {
        // The photo came in meanwhile, so a retry can't work. The server's reason says so.
        setResend({ state: "failed", why: error.detail ?? "This trip no longer needs a link." });
      } else {
        setResend({ state: "failed", why: "Not sent. Try again." });
      }
    }
  }

  return (
    <>
      <button
        className="btn btn--card btn--sm"
        type="button"
        disabled={resend.state === "sending"}
        onClick={() => void send()}
      >
        {resend.state === "sending" ? "Sending…" : "Resend SMS link"}
      </button>
      {resend.state === "sent" && (
        <span className="muted dashboard__sent" role="status">
          Mock SMS sent to {resend.to}
        </span>
      )}
      {resend.state === "sent" && resend.token && (
        <MockSmsToast
          sms={{ sentTo: resend.to, token: resend.token }}
          onClose={() => setResend({ ...resend, token: null })}
        />
      )}
      {resend.state === "failed" && (
        <span className="dashboard__sent dashboard__sent--failed" role="alert">
          {resend.why}
        </span>
      )}
    </>
  );
}

function MissingRow({ row, onSignedOut }: { row: MissingPod; onSignedOut: () => void }) {
  return (
    <tr>
      <td className="fig">{row.trip_code}</td>
      <td className="fig">
        {row.registration_no}
        {row.ownership === "hired" && <span className="muted small"> hired</span>}
      </td>
      <td>
        {row.client_name}, {row.destination}
      </td>
      <td>{row.branch_name}</td>
      <td>
        <span className={row.over_24_hours ? "fig dashboard__hours" : "fig"}>
          {sinceDelivery(row.hours_since_delivery)}
        </span>
        {row.over_24_hours && <span className="tag dashboard__late">over 24 h</span>}
      </td>
      <td className="r">
        <ResendLink tripId={row.trip_id} onSignedOut={onSignedOut} />
      </td>
    </tr>
  );
}

function MissingList({
  rows,
  onReload,
  onSignedOut,
}: {
  rows: MissingPod[];
  onReload: () => void;
  onSignedOut: () => void;
}) {
  if (rows.length === 0) {
    return (
      <div className="dashboard__empty">
        <p>No delivered trip is waiting for a POD.</p>
        <p className="muted">Trips land here once they pass expected delivery with no usable photo.</p>
        <button className="btn btn--card" type="button" onClick={onReload}>
          Check again
        </button>
      </div>
    );
  }

  return (
    <div className="scroll">
      <table className="tbl dashboard__table">
        <thead>
          <tr>
            <th>Trip</th>
            <th>Vehicle</th>
            <th>Client and destination</th>
            <th>Branch</th>
            <th>Since delivery</th>
            <th className="r">
              <span className="visually-hidden">Action</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <MissingRow key={row.trip_id} row={row} onSignedOut={onSignedOut} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BranchBars({ branches, onReload }: { branches: BranchDays[]; onReload: () => void }) {
  if (branches.length === 0) {
    return (
      <div className="dashboard__empty">
        <p className="muted">A branch appears once one of its trips has been invoiced.</p>
        <button className="btn btn--card" type="button" onClick={onReload}>
          Check again
        </button>
      </div>
    );
  }

  // A branch far past the target still has to fit, so the scale grows with the slowest one.
  const scale = Math.max(SCALE_MINIMUM_DAYS, ...branches.map((branch) => branch.median_days));
  const position = (days: number) => `${(days / scale) * 100}%`;
  return (
    <>
      {branches.map((branch) => (
        <div className="dashboard__branch" key={branch.branch_name}>
          <span>{branch.branch_name}</span>
          <span className="dashboard__track" aria-hidden="true">
            <span className="dashboard__bar" style={{ width: position(branch.median_days) }} />
            <span className="dashboard__target" style={{ left: position(TARGET_INVOICE_DAYS) }} />
          </span>
          <span className="fig r">{branch.median_days.toFixed(1)}</span>
        </div>
      ))}
    </>
  );
}

export default function MissingPods() {
  const { setUser } = useSession();
  const [page, setPage] = useState<Loadable<Dashboard>>({ state: "loading" });
  const signedOut = useCallback(() => setUser(null), [setUser]);

  const load = useCallback(async () => {
    setPage({ state: "loading" });
    try {
      setPage({ state: "ready", value: await getDashboard() });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) signedOut();
      else setPage({ state: "error" });
    }
  }, [signedOut]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <div className="head">
        <h1>Missing PODs</h1>
        {page.state === "ready" && (
          <p className="muted">Sample data. Figures cover the last {page.value.window_days} days</p>
        )}
      </div>

      {page.state === "loading" && <Skeleton />}
      {page.state === "error" && <ErrorState onRetry={() => void load()} />}
      {page.state === "ready" && (
        <>
          <Figures dashboard={page.value} />
          <div className="dashboard__grid">
            <section>
              <h2>Delivered, still no POD</h2>
              <MissingList
                rows={page.value.missing}
                onReload={() => void load()}
                onSignedOut={signedOut}
              />
            </section>
            <section>
              <h2>Days from POD to invoice</h2>
              <p className="muted dashboard__bars-note">
                Median by branch. The dashed line is the {TARGET_INVOICE_DAYS}-day target.
              </p>
              <BranchBars branches={page.value.branches} onReload={() => void load()} />
              <ClientLinkPanel onSignedOut={signedOut} />
            </section>
          </div>
        </>
      )}
    </>
  );
}
