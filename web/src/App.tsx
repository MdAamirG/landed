import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router";

import DemoPicker from "./demo/DemoPicker";
import DriverTrip from "./driver/DriverTrip";
import Billing from "./office/Billing";
import { DESTINATIONS } from "./office/destinations";
import MissingPods from "./office/MissingPods";
import { OfficeHome, OfficeLayout, RoleGate } from "./office/OfficeLayout";
import Placeholder from "./office/Placeholder";
import Review from "./office/Review";
import { SessionProvider } from "./office/session";
import SignIn from "./office/SignIn";
import Trips from "./office/Trips";
import Status from "./Status";

// The destinations built so far. Anything else shows the placeholder until its ticket lands.
const SCREENS: Record<string, ReactNode> = {
  review: <Review />,
  billing: <Billing />,
  "missing-pods": <MissingPods />,
  trips: <Trips />,
};

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/office" replace />} />
        <Route path="/status" element={<Status />} />
        <Route path="/d/:token" element={<DriverTrip />} />
        <Route path="/demo" element={<DemoPicker />} />

        {/* Only the office area loads the session. The driver area never touches it. */}
        <Route
          element={
            <SessionProvider>
              <Outlet />
            </SessionProvider>
          }
        >
          <Route path="/sign-in" element={<SignIn />} />
          <Route path="/office" element={<OfficeLayout />}>
            <Route index element={<OfficeHome />} />
            {DESTINATIONS.map((destination) => (
              <Route
                key={destination.path}
                path={destination.path}
                element={
                  <RoleGate roles={destination.roles}>
                    {SCREENS[destination.path] ?? <Placeholder title={destination.label} />}
                  </RoleGate>
                }
              />
            ))}
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/office" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
