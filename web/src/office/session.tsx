import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getCurrentUser, type OfficeUser } from "../lib/api";

type SessionState =
  | { status: "loading" }
  | { status: "signed-out" }
  | { status: "signed-in"; user: OfficeUser }
  | { status: "unreachable" }; // The API didn't answer, so we can't say either way.

type Session = {
  session: SessionState;
  setUser: (user: OfficeUser | null) => void;
  reload: () => void;
};

const SessionContext = createContext<Session | null>(null);

/** Asks the API who is signed in. The cookie is http-only, so the page can't read it itself. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionState>({ status: "loading" });

  const setUser = useCallback((user: OfficeUser | null) => {
    setSession(user ? { status: "signed-in", user } : { status: "signed-out" });
  }, []);

  const reload = useCallback(() => {
    setSession({ status: "loading" });
    getCurrentUser()
      .then(setUser)
      .catch(() => setSession({ status: "unreachable" }));
  }, [setUser]);

  useEffect(reload, [reload]);

  const value = useMemo(() => ({ session, setUser, reload }), [session, setUser, reload]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
