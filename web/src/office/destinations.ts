import type { QueueCounts, Role } from "../lib/api";

export type Destination = {
  path: string;
  label: string;
  roles: Role[];
  count?: keyof QueueCounts; // The queue whose size shows beside the label.
};

// The top bar's four destinations. Roles follow the table in docs/data-model.md: the operations
// head can't approve or export, so only the screens they can use appear for them. The server
// enforces this on every route; hiding a link just avoids a dead end.
export const DESTINATIONS: Destination[] = [
  { path: "review", label: "Review", roles: ["billing_executive"], count: "review" },
  { path: "billing", label: "Billing", roles: ["billing_executive"], count: "billing" },
  {
    path: "missing-pods",
    label: "Missing PODs",
    roles: ["billing_executive", "operations_head"],
    count: "missing_pods",
  },
  { path: "trips", label: "Trips", roles: ["billing_executive"] },
];

export const ROLE_LABELS: Record<Role, string> = {
  billing_executive: "Billing executive",
  operations_head: "Operations head",
};
