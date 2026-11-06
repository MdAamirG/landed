import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

import { photoQueue } from "../driver/photoQueue";
import { ApiError, getDemoScenarios, startDemoScenario, type DemoScenario } from "../lib/api";

type Page =
  | { state: "loading" }
  | { state: "off" }
  | { state: "error" }
  | { state: "ready"; scenarios: DemoScenario[] };

function ScenarioRow({
  scenario,
  busy,
  onPick,
}: {
  scenario: DemoScenario;
  busy: boolean;
  onPick: () => void;
}) {
  return (
    <button className="demo-scenario stock" type="button" disabled={busy} onClick={onPick}>
      <span className="demo-scenario__title">{scenario.title}</span>
      <span className="muted">{scenario.expected}</span>
      <span className="fig muted small">{scenario.trip_code}</span>
    </button>
  );
}

/** The five scenarios. Picking one resets that trip and opens it as its driver would. */
export default function DemoPicker() {
  const [page, setPage] = useState<Page>({ state: "loading" });
  const [starting, setStarting] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setPage({ state: "loading" });
    try {
      setPage({ state: "ready", scenarios: await getDemoScenarios() });
    } catch (error) {
      setPage({ state: error instanceof ApiError && error.status === 404 ? "off" : "error" });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function pick(scenario: DemoScenario) {
    setStarting(scenario.id);
    setFailed(false);
    try {
      const token = await startDemoScenario(scenario.id);
      // A photo left over from the last try holds the old link, which the reset has just killed.
      await photoQueue.discard(scenario.trip_code);
      navigate(`/d/${token}`);
    } catch {
      setFailed(true);
      setStarting(null);
    }
  }

  return (
    <main className="driver desk">
      <h1 className="driver__title">Driver demo</h1>

      {page.state === "loading" && <p className="muted">Loading the scenarios…</p>}
      {page.state === "off" && (
        <>
          <p className="muted">The demo isn't turned on for this build.</p>
          <Link to="/sign-in">Go to sign in</Link>
        </>
      )}
      {page.state === "error" && (
        <>
          <p className="muted">We couldn't reach Landed. Check your connection and try again.</p>
          <button className="btn btn--ink" type="button" onClick={() => void load()}>
            Try again
          </button>
        </>
      )}
      {page.state === "ready" && (
        <>
          <p className="muted">
            Pick a delivery. Each one starts again from the beginning, then goes through the real
            AI check. Use the sample photo, or take your own: yours keeps its real date and
            location, so it may go to Review.
          </p>
          {failed && (
            <p className="form-error" role="alert">
              That scenario didn't start. Try again.
            </p>
          )}
          {page.scenarios.map((scenario) => (
            <ScenarioRow
              key={scenario.id}
              scenario={scenario}
              busy={starting !== null}
              onPick={() => void pick(scenario)}
            />
          ))}
        </>
      )}
    </main>
  );
}
