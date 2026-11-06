export type ApiHealth = "healthy" | "database-down" | "api-down";

// Longer than the API's usual response, but short enough to show the error state and a retry.
const HEALTH_TIMEOUT_MS = 15_000;

export async function checkApiHealth(): Promise<ApiHealth> {
  try {
    const response = await fetch("/api/health", {
      signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
    });
    // Read the body rather than the status code: a host's HTML fallback page can also return 200,
    // and json() throws on it, so it counts as the API being down.
    const body: { status?: string; database?: string } = await response.json();
    if (body.status === "ok") return "healthy";
    if (body.database === "unreachable") return "database-down";
    return "api-down";
  } catch {
    return "api-down";
  }
}

export type Role = "billing_executive" | "operations_head";

export type OfficeUser = { name: string; email: string; role: Role };

/** A request that failed. Status 0 means no answer came back at all. */
export class ApiError extends Error {
  constructor(public status: number) {
    super(`API request failed with status ${status}`);
  }
}

// A cold Render service and a suspended Neon database can both be slow to answer.
const REQUEST_TIMEOUT_MS = 30_000;

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch {
    throw new ApiError(0);
  }
  if (!response.ok) throw new ApiError(response.status);
  return response;
}

function postJson(path: string, body: unknown): Promise<Response> {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** The signed-in user, or null if there is no session. Throws if the API can't be reached. */
export async function getCurrentUser(): Promise<OfficeUser | null> {
  try {
    return (await (await request("/auth/me")).json()) as OfficeUser;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export async function login(email: string, password: string): Promise<OfficeUser> {
  return (await (await postJson("/auth/login", { email, password })).json()) as OfficeUser;
}

export async function demoLogin(role: Role): Promise<OfficeUser> {
  return (await (await postJson("/auth/demo-login", { role })).json()) as OfficeUser;
}

export async function logout(): Promise<void> {
  await request("/auth/logout", { method: "POST" });
}

export async function isDemoMode(): Promise<boolean> {
  const options = (await (await request("/auth/options")).json()) as { demo_mode: boolean };
  return options.demo_mode;
}
