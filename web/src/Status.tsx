import { useCallback, useEffect, useState } from "react";

import { checkApiHealth, type ApiHealth } from "./lib/api";

type HealthCheck = ApiHealth | "pending";

const MESSAGES: Record<HealthCheck, { title: string; detail: string }> = {
  pending: { title: "Checking the API", detail: "This takes a moment." },
  healthy: { title: "API reachable", detail: "The API and the database are both up." },
  "database-down": {
    title: "Database unreachable",
    detail: "The API is up, but it can't reach the database. Try again in a minute.",
  },
  "api-down": {
    title: "API unreachable",
    detail: "Check that the API is running, then try again.",
  },
};

export default function Status() {
  const [health, setHealth] = useState<HealthCheck>("pending");

  const check = useCallback(async () => {
    setHealth("pending");
    setHealth(await checkApiHealth());
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  const { title, detail } = MESSAGES[health];
  const failed = health === "database-down" || health === "api-down";

  return (
    <main className="health">
      <p className="word">Landed</p>
      <section className="stock health__card" role="status">
        <h1>{title}</h1>
        <p className="muted">{detail}</p>
        {failed && (
          <button className="btn btn--ink" type="button" onClick={() => void check()}>
            Try again
          </button>
        )}
      </section>
    </main>
  );
}
