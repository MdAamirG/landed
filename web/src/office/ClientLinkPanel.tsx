import { useCallback, useEffect, useState } from "react";

import { ApiError, getLinkClients, makeClientLink, type ClientChoice } from "../lib/api";
import type { Loadable } from "./LoadStates";

type Made =
  | { state: "idle" | "making" }
  | { state: "made"; url: string; expiresAt: string; copied: boolean }
  | { state: "failed" };

function indiaDate(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: "Asia/Kolkata",
  }).format(new Date(iso));
}

/** "Client POD link" from Dashboard.html, with a client picker, since a link opens one client. */
export default function ClientLinkPanel({ onSignedOut }: { onSignedOut: () => void }) {
  const [clients, setClients] = useState<Loadable<ClientChoice[]>>({ state: "loading" });
  const [clientId, setClientId] = useState("");
  const [made, setMade] = useState<Made>({ state: "idle" });

  const load = useCallback(async () => {
    setClients({ state: "loading" });
    try {
      const found = await getLinkClients();
      setClients({ state: "ready", value: found });
      setClientId((current) => current || (found[0]?.id ?? ""));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) onSignedOut();
      else setClients({ state: "error" });
    }
  }, [onSignedOut]);

  useEffect(() => {
    void load();
  }, [load]);

  async function make() {
    setMade({ state: "making" });
    try {
      const link = await makeClientLink(clientId);
      let copied = false;
      try {
        await navigator.clipboard.writeText(link.url);
        copied = true;
      } catch {
        // No clipboard (an http page, or permission refused). The link is shown to copy by hand.
      }
      setMade({ state: "made", url: link.url, expiresAt: link.expires_at, copied });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) onSignedOut();
      else setMade({ state: "failed" });
    }
  }

  return (
    <div className="client-link">
      <p>
        <span className="client-link__title">Client POD link</span>
        <br />
        <span className="muted small">Read-only, expires after 7 days</span>
      </p>

      {clients.state === "loading" && (
        <p className="muted small" role="status">
          Loading clients…
        </p>
      )}
      {clients.state === "error" && (
        <p className="small" role="alert">
          Couldn't load the clients.{" "}
          <button className="btn btn--card btn--sm" type="button" onClick={() => void load()}>
            Try again
          </button>
        </p>
      )}
      {clients.state === "ready" && clients.value.length === 0 && (
        <p className="muted small">No clients yet. Import trips first.</p>
      )}
      {clients.state === "ready" && clients.value.length > 0 && (
        <div className="client-link__make">
          <label className="muted billing__filter">
            Client
            <select
              value={clientId}
              onChange={(event) => {
                setClientId(event.target.value);
                setMade({ state: "idle" }); // A link shown for the last client would mislead.
              }}
            >
              {clients.value.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.name}
                </option>
              ))}
            </select>
          </label>
          <button
            className="btn btn--card btn--sm"
            type="button"
            disabled={made.state === "making" || !clientId}
            onClick={() => void make()}
          >
            {made.state === "making" ? "Making…" : "Copy link"}
          </button>
        </div>
      )}

      {made.state === "made" && (
        <div className="client-link__made" role="status">
          <p className="small">
            {made.copied ? "Copied. " : "Copy this link. "}
            It works until {indiaDate(made.expiresAt)}.
          </p>
          <input
            className="client-link__url"
            readOnly
            value={made.url}
            aria-label="Client POD link"
            onFocus={(event) => event.target.select()}
          />
          <a className="small" href={made.url} target="_blank" rel="noopener">
            Open it as the client sees it
          </a>
        </div>
      )}
      {made.state === "failed" && (
        <p className="small dashboard__sent--failed" role="alert">
          No link made. Try again.
        </p>
      )}
    </div>
  );
}
