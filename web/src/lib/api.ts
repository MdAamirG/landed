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
