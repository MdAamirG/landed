import type { PreparedPhoto } from "../driver/capture";

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

export type PodStatus =
  | "awaiting_pod"
  | "checking"
  | "retake_requested"
  | "needs_review"
  | "verified"
  | "disputed"
  | "invoiced";

/** What a demo trip's driver screen sends with its sample photo. */
export type DemoSample = {
  scenario: string;
  captured_at: string;
  gps_lat: number;
  gps_lng: number;
};

export type DriverTrip = {
  trip_code: string;
  registration_no: string;
  client_name: string;
  origin: string;
  destination: string;
  lr_number: string;
  eway_bill_no: string;
  pod_status: PodStatus;
  retakes_used: number;
  reason_codes: string[];
  demo_sample: DemoSample | null;
};

export type Role = "billing_executive" | "operations_head";

export type OfficeUser = { name: string; email: string; role: Role };

/** A request that failed. Status 0 means no answer came back at all. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string | null = null, // The server's own words, such as which trips moved.
  ) {
    super(`API request failed with status ${status}`);
  }
}

async function errorDetail(response: Response): Promise<string | null> {
  try {
    const body: { detail?: unknown } = await response.json();
    return typeof body.detail === "string" ? body.detail : null; // A 422's detail is a list.
  } catch {
    return null;
  }
}

// A cold Render service and a suspended Neon database can both be slow to answer.
const REQUEST_TIMEOUT_MS = 30_000;
// 300 KB can take most of a minute to go up on a weak 2G signal.
const UPLOAD_TIMEOUT_MS = 120_000;

async function request(
  path: string,
  init: RequestInit = {},
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch {
    throw new ApiError(0);
  }
  if (!response.ok) throw new ApiError(response.status, await errorDetail(response));
  return response;
}

function sendJson(method: "POST" | "PATCH", path: string, body: unknown): Promise<Response> {
  return request(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function postJson(path: string, body: unknown): Promise<Response> {
  return sendJson("POST", path, body);
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

export type DemoScenario = { id: string; trip_code: string; title: string; expected: string };

export async function getDemoScenarios(): Promise<DemoScenario[]> {
  return (await (await request("/demo/scenarios")).json()) as DemoScenario[];
}

/** Resets the scenario's trip and returns a token for its fresh driver link. */
export async function startDemoScenario(scenarioId: string): Promise<string> {
  const response = await request(`/demo/scenarios/${scenarioId}/start`, { method: "POST" });
  return ((await response.json()) as { driver_token: string }).driver_token;
}

/** The token goes in a header, not the API path, so it stays out of the API's request logs. */
export async function getDriverTrip(token: string): Promise<DriverTrip> {
  const response = await request("/driver/trip", { headers: driverHeaders(token) });
  return (await response.json()) as DriverTrip;
}

export type AttemptResult = {
  attempt_id: string;
  attempt_no: number;
  outcome: PodStatus | null;
  reason_codes: string[];
  retakes_used: number;
};

function driverHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export async function uploadAttempt(
  token: string,
  attemptId: string,
  photo: PreparedPhoto,
): Promise<AttemptResult> {
  const form = new FormData();
  form.set("attempt_id", attemptId);
  form.set("captured_at", photo.capturedAt.toISOString());
  form.set("device_check", photo.deviceCheck);
  if (photo.gps) {
    form.set("gps_lat", String(photo.gps.lat));
    form.set("gps_lng", String(photo.gps.lng));
    form.set("gps_accuracy_m", String(photo.gps.accuracyM));
  }
  form.set("photo", photo.blob, "pod.jpg");
  const response = await request(
    "/driver/attempts",
    { method: "POST", headers: driverHeaders(token), body: form },
    UPLOAD_TIMEOUT_MS,
  );
  return (await response.json()) as AttemptResult;
}

export async function getAttempt(token: string, attemptId: string): Promise<AttemptResult> {
  const response = await request(`/driver/attempts/${attemptId}`, {
    headers: driverHeaders(token),
  });
  return (await response.json()) as AttemptResult;
}

export type PodFieldName =
  | "lr_number"
  | "consignee_stamp"
  | "quantity_received"
  | "remarks"
  | "delivery_date"
  | "signature";

export type Quantity = { number: number | null; unit: string | null };
export type Remarks = { text: string | null; kind: string };
export type FieldValue = string | Quantity | Remarks | null;

export type ReviewField = {
  field: PodFieldName;
  ai_value: FieldValue;
  ai_confidence: number | null;
  final_value: FieldValue;
  edited: boolean;
};

export type ReviewAttempt = {
  id: string;
  attempt_no: number;
  late: boolean;
  captured_at: string;
  received_at: string;
  size_bytes: number;
  distance_km: number | null;
  device_check: "passed" | "sent_anyway" | null;
  ai_status: string | null;
  ai_latency_ms: number | null;
  reason_codes: string[];
  clock_corrected: boolean;
  fields: ReviewField[];
};

export type ReviewTrip = {
  id: string;
  trip_code: string;
  version: number;
  pod_status: PodStatus;
  status_reason: string | null;
  reason_codes: string[];
  retakes_used: number;
  origin: string;
  destination: string;
  client_name: string;
  ownership: "own" | "hired";
  registration_no: string;
  lr_number: string;
  eway_bill_no: string;
  qty_dispatched: number;
  qty_unit: string;
  consignee_name: string;
  consignee_phone: string;
  driver_name: string;
  driver_phone: string;
  current_attempt_id: string | null;
  attempts: ReviewAttempt[];
  checks: { label: string; ok: boolean }[];
};

export type ReviewQueueItem = {
  id: string;
  trip_code: string;
  destination: string;
  client_name: string;
  ownership: "own" | "hired";
  status_reason: string | null;
  waiting_since: string;
  late_photos: number;
};

export type ReviewFilter = "needs_review" | "disputed" | "verified";

export async function getReviewQueue(filter: ReviewFilter): Promise<ReviewQueueItem[]> {
  return (await (await request(`/review/queue?filter=${filter}`)).json()) as ReviewQueueItem[];
}

export async function getReviewTrip(tripId: string): Promise<ReviewTrip> {
  return (await (await request(`/review/trips/${tripId}`)).json()) as ReviewTrip;
}

export function attemptPhotoUrl(attemptId: string): string {
  return `/api/review/attempts/${attemptId}/photo`;
}

export async function saveField(
  tripId: string,
  field: PodFieldName,
  value: FieldValue,
  version: number,
): Promise<ReviewTrip> {
  const response = await sendJson("PATCH", `/review/trips/${tripId}/fields/${field}`, {
    value,
    version,
  });
  return (await response.json()) as ReviewTrip;
}

export type ReviewAction = "approve" | "retake" | "dispute" | "pull-back";

export async function actOnTrip(
  tripId: string,
  action: ReviewAction,
  version: number,
): Promise<ReviewTrip> {
  const response = await postJson(`/review/trips/${tripId}/${action}`, { version });
  return (await response.json()) as ReviewTrip;
}

export async function revealContact(tripId: string): Promise<{ name: string; phone: string }> {
  const response = await postJson(`/review/trips/${tripId}/reveal`, {});
  return (await response.json()) as { name: string; phone: string };
}

export type BillingTrip = {
  id: string;
  trip_code: string;
  destination: string;
  lr_number: string;
  remark: string | null;
  freight_paise: number;
};

export type BillingClient = { client_id: string; client_name: string; trips: BillingTrip[] };

export type BillingCycle = { start: string; end: string; trip_count: number };

export type BillingQueue = {
  cycles: BillingCycle[];
  cycle_start: string | null;
  clients: BillingClient[];
  in_review: number;
};

export type ExportSummary = {
  id: string;
  trip_count: number;
  total_paise: number;
  exported_at: string;
};

export async function getBillingQueue(cycle: string | null): Promise<BillingQueue> {
  const query = cycle ? `?cycle=${cycle}` : "";
  return (await (await request(`/billing/queue${query}`)).json()) as BillingQueue;
}

export async function getExports(): Promise<ExportSummary[]> {
  return (await (await request("/billing/exports")).json()) as ExportSummary[];
}

export async function createExport(tripIds: string[]): Promise<ExportSummary> {
  return (await (await postJson("/billing/exports", { trip_ids: tripIds })).json()) as ExportSummary;
}

export function exportFileUrl(exportId: string, file: "xml" | "photos"): string {
  return `/api/billing/exports/${exportId}/${file}`;
}

export type MissingPod = {
  trip_id: string;
  trip_code: string;
  registration_no: string;
  ownership: "own" | "hired";
  client_name: string;
  destination: string;
  branch_name: string;
  hours_since_delivery: number;
  over_24_hours: boolean;
};

export type BranchDays = { branch_name: string; median_days: number };

/** A figure is null when there's nothing to measure yet, which isn't the same as zero. */
export type Dashboard = {
  window_days: number;
  missing: MissingPod[];
  within_24_hours_percent: number | null;
  pod_to_invoice_days: number | null;
  lost_or_disputed_percent: number | null;
  branches: BranchDays[];
};

export type QueueCounts = { review: number; billing: number; missing_pods: number };

export async function getDashboard(): Promise<Dashboard> {
  return (await (await request("/dashboard")).json()) as Dashboard;
}

export async function getQueueCounts(): Promise<QueueCounts> {
  return (await (await request("/dashboard/counts")).json()) as QueueCounts;
}

export async function resendDriverLink(tripId: string): Promise<{ sent_to: string }> {
  const path = `/dashboard/trips/${tripId}/resend-link`;
  return (await (await request(path, { method: "POST" })).json()) as { sent_to: string };
}
