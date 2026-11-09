import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router";

import {
  ApiError,
  getClientPodPhoto,
  getClientPods,
  type ClientPod,
  type ClientPods,
} from "../lib/api";
import { ErrorState, Skeleton } from "../office/LoadStates";

/** What a client's accounts team sees from a client POD link (story 77). Read-only throughout. */

type Page =
  | { state: "loading" }
  | { state: "dead-link" }
  | { state: "error" }
  | { state: "ready"; value: ClientPods };

type Photo =
  | { state: "closed" }
  | { state: "loading"; pod: ClientPod }
  | { state: "error"; pod: ClientPod }
  | { state: "ready"; pod: ClientPod; url: string };

function indiaDate(iso: string, withTime = false): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit", hourCycle: "h23" } : {}),
    timeZone: "Asia/Kolkata",
  }).format(new Date(iso));
}

function PodRow({ pod, onView }: { pod: ClientPod; onView: () => void }) {
  return (
    <tr>
      <td className="fig">{pod.trip_code}</td>
      <td className="fig">{pod.lr_number}</td>
      <td className="fig">{pod.eway_bill_no}</td>
      <td>
        {pod.origin} to {pod.destination}
        <span className="muted small client-pods__consignee"> {pod.consignee_name}</span>
      </td>
      <td>{indiaDate(pod.delivered_at)}</td>
      <td>
        {pod.invoiced ? (
          <>
            Invoiced <span className="fig muted small">{pod.voucher_no}</span>
          </>
        ) : (
          "Checked"
        )}
        {pod.remark && <span className="muted small client-pods__remark">{pod.remark}</span>}
      </td>
      <td className="r">
        <button className="btn btn--card btn--sm" type="button" onClick={onView}>
          View POD
        </button>
      </td>
    </tr>
  );
}

function PhotoDialog({
  photo,
  onClose,
  onRetry,
}: {
  photo: Photo;
  onClose: () => void;
  onRetry: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    // A native modal dialog: it traps focus, and Escape closes it.
    if (photo.state !== "closed" && !dialog.current?.open) dialog.current?.showModal();
    if (photo.state === "closed" && dialog.current?.open) dialog.current.close();
  }, [photo.state]);

  return (
    <dialog ref={dialog} className="client-pods__dialog stock" onClose={onClose}>
      {photo.state !== "closed" && (
        <>
          <div className="client-pods__dialog-head">
            <h2>
              POD for <span className="fig">{photo.pod.trip_code}</span>
            </h2>
            <button className="btn btn--card btn--sm" type="button" onClick={onClose}>
              Close
            </button>
          </div>
          {photo.state === "loading" && (
            <p className="muted" role="status">
              Loading the photo…
            </p>
          )}
          {photo.state === "error" && (
            <p role="alert">
              We couldn't load the photo.{" "}
              <button className="btn btn--card btn--sm" type="button" onClick={onRetry}>
                Try again
              </button>
            </p>
          )}
          {photo.state === "ready" && (
            <img
              className="client-pods__photo"
              src={photo.url}
              alt={`Signed lorry receipt for ${photo.pod.trip_code}, LR ${photo.pod.lr_number}`}
            />
          )}
        </>
      )}
    </dialog>
  );
}

export default function ClientPodsPage() {
  const { token = "" } = useParams();
  const [page, setPage] = useState<Page>({ state: "loading" });
  const [photo, setPhoto] = useState<Photo>({ state: "closed" });

  const load = useCallback(async () => {
    setPage({ state: "loading" });
    try {
      setPage({ state: "ready", value: await getClientPods(token) });
    } catch (error) {
      // Expired, tampered and unknown all look the same here: ask for a new link.
      if (error instanceof ApiError && error.status === 401) setPage({ state: "dead-link" });
      else setPage({ state: "error" });
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  // The blob URL holds the photo in memory until it is let go.
  useEffect(() => {
    if (photo.state !== "ready") return;
    return () => URL.revokeObjectURL(photo.url);
  }, [photo]);

  async function view(pod: ClientPod) {
    setPhoto({ state: "loading", pod });
    try {
      const blob = await getClientPodPhoto(token, pod.trip_id);
      setPhoto({ state: "ready", pod, url: URL.createObjectURL(blob) });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setPhoto({ state: "closed" });
        setPage({ state: "dead-link" }); // The link expired while the page was open.
      } else {
        setPhoto({ state: "error", pod });
      }
    }
  }

  if (page.state === "dead-link") {
    return (
      <main className="notice notice--page" role="alert">
        <h1>This link doesn't work</h1>
        <p className="muted">
          It may have expired, since a link lasts 7 days. Ask the transporter for a new one.
        </p>
      </main>
    );
  }

  return (
    <>
      <header className="top">
        <span className="word">Landed</span>
      </header>
      <main className="wrap">
        {page.state === "loading" && <Skeleton />}
        {page.state === "error" && <ErrorState onRetry={() => void load()} />}
        {page.state === "ready" && (
          <>
            <div className="head">
              <h1>PODs for {page.value.client_name}</h1>
              <p className="muted">
                Read-only. This link works until {indiaDate(page.value.expires_at, true)}.
              </p>
            </div>
            {page.value.pods.length === 0 ? (
              <div className="dashboard__empty">
                <p>No PODs to show yet.</p>
                <p className="muted">A POD appears here once the transporter has checked it.</p>
                <button className="btn btn--card" type="button" onClick={() => void load()}>
                  Check again
                </button>
              </div>
            ) : (
              <div className="scroll">
                <table className="tbl client-pods__table">
                  <thead>
                    <tr>
                      <th>Trip</th>
                      <th>LR</th>
                      <th>E-way bill</th>
                      <th>Route and consignee</th>
                      <th>Delivered</th>
                      <th>Status</th>
                      <th className="r">
                        <span className="visually-hidden">Photo</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {page.value.pods.map((pod) => (
                      <PodRow key={pod.trip_id} pod={pod} onView={() => void view(pod)} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </main>
      <PhotoDialog
        photo={photo}
        onClose={() => setPhoto({ state: "closed" })}
        onRetry={() => {
          if (photo.state !== "closed") void view(photo.pod);
        }}
      />
    </>
  );
}
