import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router";

import { DESTINATIONS } from "./office/destinations";
import { OfficeHome, OfficeLayout, RoleGate } from "./office/OfficeLayout";
import Placeholder from "./office/Placeholder";
import { SessionProvider } from "./office/session";
import SignIn from "./office/SignIn";
import Status from "./Status";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/office" replace />} />
        <Route path="/status" element={<Status />} />

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
                    <Placeholder title={destination.label} />
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
