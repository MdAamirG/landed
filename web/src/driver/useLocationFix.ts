import { useEffect, useState } from "react";

import type { GpsFix } from "./capture";

/** The phone's latest position, or null. It runs from the moment the trip opens, so a fix is
 * usually ready when the photo is taken. No location never stops a photo: dead zones are expected.
 */
export function useLocationFix(): GpsFix | null {
  const [fix, setFix] = useState<GpsFix | null>(null);

  useEffect(() => {
    if (!("geolocation" in navigator)) return;
    const watch = navigator.geolocation.watchPosition(
      ({ coords }) =>
        setFix({ lat: coords.latitude, lng: coords.longitude, accuracyM: coords.accuracy }),
      () => undefined, // Refused or unavailable: the photo goes without a location.
      { enableHighAccuracy: true, maximumAge: 60_000 },
    );
    return () => navigator.geolocation.clearWatch(watch);
  }, []);

  return fix;
}
