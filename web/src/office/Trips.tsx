import { useCallback, useRef, useState, type ChangeEvent, type ReactNode } from "react";

import {
  ApiError,
  checkTripFile,
  importTripFile,
  type ImportResult,
  type ImportRow,
} from "../lib/api";
import { rupees } from "../lib/format";
import { ErrorState, Skeleton } from "./LoadStates";
import { useSession } from "./session";

// Two steps, as in Trips.html: check the file, look at each row, then import. The browser keeps
// the file and sends it again for the import, so nothing waits on the server between the steps.
type Step =
  | { state: "empty" }
  | { state: "checking"; file: File }
  | { state: "checked"; file: File; result: ImportResult; at: Date }
  | { state: "importing"; file: File; result: ImportResult; at: Date }
  | { state: "imported"; file: File; result: ImportResult; at: Date }
  | { state: "refused"; file: File; why: string } // The file as a whole can't be read.
  | { state: "failed"; file: File; retry: () => void }; // No answer, or the server broke.

type ChooseButton = (label: string, className?: string) => ReactNode;

function indiaTime(moment: Date): string {
  return new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: "Asia/Kolkata",
  }).format(moment);
}

/** "341099220418" reads more easily as "3410 9922 0418", as on the e-way bill itself. */
function ewayShown(eway: string): string {
  return /^\d{12}$/.test(eway) ? eway.replace(/(\d{4})(?=\d)/g, "$1 ") : eway;
}

function plural(amount: number, one: string): string {
  return `${amount} ${one}${amount === 1 ? "" : "s"}`;
}

/**
 * The rows to fix, copied line for line out of the file the executive chose, with each row's
 * problems in a last column. Built here rather than on the server, so consignee names and phones
 * never come back in a response. The server ignores the extra column when the file comes back.
 */
function rowsToFix(text: string, rows: ImportRow[]): string {
  const lines = text.split(/\r\n|\r|\n/); // The same line breaks Python's csv reader counts.
  const quoted = (cell: string) => `"${cell.replaceAll('"', '""')}"`;
  const out = [`${lines[0]},problem`];
  for (const row of rows.filter((row) => row.problems.length > 0)) {
    const record = lines.slice(row.first_line - 1, row.last_line);
    record[record.length - 1] += `,${quoted(row.problems.join("; "))}`;
    out.push(...record);
  }
  return `﻿${out.join("\r\n")}\r\n`; // The mark tells Excel the file is UTF-8.
}

async function downloadRowsToFix(file: File, rows: ImportRow[]): Promise<void> {
  const blob = new Blob([rowsToFix(await file.text(), rows)], { type: "text/csv" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${file.name.replace(/\.csv$/i, "")}-to-fix.csv`;
  link.click();
  // Later rather than at once, which some browsers take as cancelling the download.
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

function Tick() {
  return (
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
      <path d="M5 12l5 5 9-10" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg
      width="26"
      height="26"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M14 3H6v18h12V7z" />
      <path d="M14 3v4h4M9 13h6M9 17h6" />
    </svg>
  );
}

function RowCheck({ row }: { row: ImportRow }) {
  if (row.problems.length > 0) {
    return (
      <ul className="trips__problems">
        {row.problems.map((problem) => (
          <li key={problem}>{problem}</li>
        ))}
      </ul>
    );
  }
  return (
    <span className="trips__ok">
      <Tick />
      {row.imported ? "Mock SMS sent" : "Ready"}
      {/* DEMO_MODE only: there's no phone to receive the mock SMS, so the reviewer opens it. */}
      {row.driver_token && (
        <a
          className="btn btn--card btn--sm"
          href={`/d/${row.driver_token}`}
          target="_blank"
          rel="noopener"
        >
          Open link
        </a>
      )}
    </span>
  );
}

function RowsTable({ rows }: { rows: ImportRow[] }) {
  return (
    <div className="scroll">
      <table className="tbl trips__table">
        <thead>
          <tr>
            <th>Trip</th>
            <th>LR</th>
            <th>E-way bill</th>
            <th>Client and destination</th>
            <th>Vehicle</th>
            <th>Own or hired</th>
            <th className="r">Freight, ₹</th>
            <th>Check</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.first_line} className={row.problems.length ? "trips__bad" : undefined}>
              <td className="fig">{row.trip_code}</td>
              <td className="fig">{row.lr_number}</td>
              <td className="fig">
                {row.eway_bill_no ? (
                  ewayShown(row.eway_bill_no)
                ) : (
                  <span className="trips__missing">missing</span>
                )}
              </td>
              <td>
                {row.client_name}
                {row.destination && `, ${row.destination}`}
              </td>
              <td className="fig">{row.registration_no}</td>
              <td>{row.ownership}</td>
              <td className="fig r">
                {row.freight_paise === null ? "" : rupees(row.freight_paise)}
              </td>
              <td>
                <RowCheck row={row} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CheckedFile({
  step,
  chooseButton,
  onImport,
}: {
  step: Extract<Step, { state: "checked" | "importing" | "imported" }>;
  chooseButton: ChooseButton;
  onImport: () => void;
}) {
  const { file, result, at } = step;
  const toFix = result.rows_total - result.rows_ok;
  const imported = step.state === "imported";

  let importLabel = `Import ${plural(result.rows_ok, "trip")}`;
  if (step.state === "importing") importLabel = "Importing…";
  else if (result.rows_ok === 0) importLabel = "Nothing to import";

  return (
    <>
      <div className="trips__bar">
        <FileIcon />
        <p>
          <span className="fig">{result.filename}</span>
          <br />
          <span className="muted small">
            {plural(result.rows_total, "row")}, checked at{" "}
            <span className="fig">{indiaTime(at)}</span>
          </span>
        </p>
        <p className="trips__counts" role="status">
          {imported
            ? `${plural(result.rows_ok, "trip")} imported, ${toFix} not imported`
            : `${result.rows_ok} ready, ${toFix} to fix`}
        </p>
        {chooseButton(imported ? "Import another file" : "Choose another file")}
      </div>

      <RowsTable rows={result.rows} />

      <div className="trips__actions">
        {!imported && (
          <button
            className="btn btn--ink"
            type="button"
            disabled={result.rows_ok === 0 || step.state === "importing"}
            onClick={onImport}
          >
            {importLabel}
          </button>
        )}
        {toFix > 0 && (
          <button
            className="btn btn--card"
            type="button"
            onClick={() => void downloadRowsToFix(file, result.rows)}
          >
            Download the {plural(toFix, "row")} to fix
          </button>
        )}
        <p className="muted small">
          {imported
            ? "Each driver has been sent an SMS upload link. Messages are mocked in this demo."
            : "Every driver gets an SMS upload link on import. Messages are mocked in this demo."}
        </p>
      </div>
    </>
  );
}

export default function Trips() {
  const { setUser } = useSession();
  const [step, setStep] = useState<Step>({ state: "empty" });
  const picker = useRef<HTMLInputElement>(null);

  const failed = useCallback(
    (error: unknown, file: File, retry: () => void) => {
      if (error instanceof ApiError && error.status === 401) setUser(null);
      else if (error instanceof ApiError && error.status === 400 && error.detail)
        setStep({ state: "refused", file, why: error.detail });
      else setStep({ state: "failed", file, retry });
    },
    [setUser],
  );

  const check = useCallback(
    async (file: File) => {
      setStep({ state: "checking", file });
      try {
        setStep({ state: "checked", file, result: await checkTripFile(file), at: new Date() });
      } catch (error) {
        failed(error, file, () => void check(file));
      }
    },
    [failed],
  );

  async function runImport(file: File, result: ImportResult, at: Date) {
    setStep({ state: "importing", file, result, at });
    try {
      setStep({ state: "imported", file, result: await importTripFile(file), at: new Date() });
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        // Someone added some of these trips meanwhile, so check again to show which.
        void check(file);
      } else {
        // A retry is safe: if the first import landed, its rows come back as already on file.
        failed(error, file, () => void runImport(file, result, at));
      }
    }
  }

  function chosen(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // So choosing the same file again, after fixing it, still counts.
    if (file) void check(file);
  }

  const chooseButton: ChooseButton = (label, className = "btn btn--card btn--sm") => (
    <button className={className} type="button" onClick={() => picker.current?.click()}>
      {label}
    </button>
  );

  return (
    <>
      <div className="head">
        <h1>Trips</h1>
        <p className="muted">
          Import today’s file. A trip needs its LR and e-way bill before a POD can be taken.
        </p>
      </div>
      <input ref={picker} type="file" accept=".csv,text/csv" hidden onChange={chosen} />

      {step.state === "empty" && (
        <div className="trips__empty">
          <FileIcon />
          <p>Choose the day’s trip file. Each row is checked before anything is imported.</p>
          <p className="muted small">
            A CSV file with one trip per row, times in India time like 2026-11-06 07:30.{" "}
            <a href="/trips-sample.csv" download>
              Download the sample file
            </a>{" "}
            to see the columns.
          </p>
          {chooseButton("Choose the trip file", "btn btn--ink")}
        </div>
      )}

      {step.state === "checking" && (
        <>
          <p className="muted trips__bar">Checking {step.file.name}…</p>
          <Skeleton />
        </>
      )}

      {step.state === "refused" && (
        <div className="notice" role="alert">
          <h1>We couldn’t read {step.file.name}</h1>
          <p className="muted">{step.why}</p>
          {chooseButton("Choose another file", "btn btn--ink")}
        </div>
      )}

      {step.state === "failed" && <ErrorState onRetry={step.retry} />}

      {(step.state === "checked" || step.state === "importing" || step.state === "imported") && (
        <CheckedFile
          step={step}
          chooseButton={chooseButton}
          onImport={() => void runImport(step.file, step.result, step.at)}
        />
      )}
    </>
  );
}
