import { useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router";

import { ApiError, demoLogin, isDemoMode, login, type OfficeUser, type Role } from "../lib/api";
import { ROLE_LABELS } from "./destinations";
import { useSession } from "./session";

const DEMO_ROLES: Role[] = ["billing_executive", "operations_head"];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) {
    return "That email or password isn't right. Check them and try again.";
  }
  return "We couldn't reach Landed. Check your connection and try again.";
}

export default function SignIn() {
  const { session, setUser } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<Role | "password" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    // Failing quietly is right here: the worst case is no demo buttons, and the form still works.
    isDemoMode()
      .then(setDemoMode)
      .catch(() => setDemoMode(false));
  }, []);

  async function attempt(action: Role | "password", signIn: () => Promise<OfficeUser>) {
    setBusy(action);
    setError(null);
    try {
      setUser(await signIn());
    } catch (failure) {
      setError(errorMessage(failure));
      setBusy(null);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void attempt("password", () => login(email, password));
  }

  if (session.status === "signed-in") return <Navigate to="/office" replace />;

  return (
    <main className="sign-in desk">
      <div className="sign-in__card stock">
        <span className="word">Landed</span>
        <h1>Sign in</h1>

        <form className="sign-in__form" onSubmit={handleSubmit}>
          <label className="field">
            Work email
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label className="field">
            Password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button className="btn btn--ink" type="submit" disabled={busy !== null}>
            {busy === "password" ? "Signing in…" : "Sign in"}
          </button>
        </form>

        {demoMode && (
          <div className="sign-in__demo">
            <p className="muted">Reviewing the build? Sign in as a demo role.</p>
            <div className="sign-in__demo-roles">
              {DEMO_ROLES.map((role) => (
                <button
                  key={role}
                  className="btn btn--card"
                  type="button"
                  disabled={busy !== null}
                  onClick={() => void attempt(role, () => demoLogin(role))}
                >
                  {busy === role ? "Signing in…" : ROLE_LABELS[role]}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
