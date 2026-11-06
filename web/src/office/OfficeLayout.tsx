import { useEffect, useState, type ReactNode } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { getQueueCounts, logout, type OfficeUser, type QueueCounts, type Role } from "../lib/api";
import { DESTINATIONS, ROLE_LABELS } from "./destinations";
import { useSession } from "./session";

function allowedDestinations(user: OfficeUser) {
  return DESTINATIONS.filter((destination) => destination.roles.includes(user.role));
}

/** Reloaded on each move between screens. Only a nicety, so a failure just leaves them out. */
function useQueueCounts(): QueueCounts | null {
  const { pathname } = useLocation();
  const [counts, setCounts] = useState<QueueCounts | null>(null);

  useEffect(() => {
    let current = true;
    getQueueCounts()
      .then((found) => {
        if (current) setCounts(found);
      })
      .catch(() => {
        if (current) setCounts(null);
      });
    return () => {
      current = false;
    };
  }, [pathname]);

  return counts;
}

function TopBar({ user }: { user: OfficeUser }) {
  const { setUser } = useSession();
  const [signingOut, setSigningOut] = useState(false);
  const counts = useQueueCounts();

  async function signOut() {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      // Back to sign-in even if the call failed: the cookie is gone or will expire on its own.
      setUser(null);
    }
  }

  return (
    <header className="top">
      <Link to="/office" className="word">
        Landed
      </Link>
      <nav className="nav" aria-label="Main">
        {allowedDestinations(user).map((destination) => (
          <NavLink key={destination.path} to={`/office/${destination.path}`}>
            {destination.label}
            {counts && destination.count && (
              <span className="count">{counts[destination.count]}</span>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="who">
        <span>{ROLE_LABELS[user.role]}</span>
        <button
          className="btn btn--card btn--sm"
          type="button"
          disabled={signingOut}
          onClick={() => void signOut()}
        >
          {signingOut ? "Signing out…" : "Sign out"}
        </button>
      </div>
    </header>
  );
}

/** The office shell. Everything under /office renders inside it, once someone is signed in. */
export function OfficeLayout() {
  const { session, reload } = useSession();

  switch (session.status) {
    case "loading":
      return (
        <main className="notice notice--page" role="status">
          <p className="muted">Checking your sign-in…</p>
        </main>
      );
    case "unreachable":
      return (
        <main className="notice notice--page" role="alert">
          <h1>We couldn't reach Landed</h1>
          <p className="muted">Check your connection, then try again.</p>
          <button className="btn btn--ink" type="button" onClick={reload}>
            Try again
          </button>
        </main>
      );
    case "signed-out":
      return <Navigate to="/sign-in" replace />;
    case "signed-in":
      return (
        <>
          <TopBar user={session.user} />
          <main className="wrap">
            <Outlet />
          </main>
        </>
      );
  }
}

/** /office with nothing after it: go to the first screen this role can use. */
export function OfficeHome() {
  const { session } = useSession();
  if (session.status !== "signed-in") return null;
  return <Navigate to={`/office/${allowedDestinations(session.user)[0].path}`} replace />;
}

/** Stops a typed URL landing on a screen whose API calls would all return 403. */
export function RoleGate({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { session } = useSession();
  if (session.status !== "signed-in") return null;
  if (roles.includes(session.user.role)) return children;

  return (
    <div className="notice">
      <h1>Your role can't open this page</h1>
      <p className="muted">Ask a billing executive if you need something from here.</p>
      <Link className="btn btn--card" to="/office">
        Go to your screens
      </Link>
    </div>
  );
}
