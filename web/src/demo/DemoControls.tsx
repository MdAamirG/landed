import { Link } from "react-router";

import type { DriverTrip } from "../lib/api";

/** What a reviewer sees on a demo trip's driver screens. A real driver's trip shows nothing. */
export default function DemoControls({
  trip,
  onUseSample,
}: {
  trip: DriverTrip;
  onUseSample?: () => void; // Left out where there's no photo to take, as on the done screen.
}) {
  if (!trip.demo_sample) return null;

  return (
    <div className="demo-controls">
      {onUseSample && (
        <button className="btn btn--card" type="button" onClick={onUseSample}>
          Use the sample photo
        </button>
      )}
      <Link to="/demo">Try another scenario</Link>
    </div>
  );
}
