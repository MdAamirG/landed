/** A data region is always one of these three, so a screen can't forget a state. */
export type Loadable<T> = { state: "loading" } | { state: "error" } | { state: "ready"; value: T };

export function Skeleton() {
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

export function ErrorState({ onRetry }: { onRetry: () => void }) {
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
