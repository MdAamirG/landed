import type { PodFieldName } from "../lib/api";

// What each reason code means to an executive. docs/data-model.md has the rule behind each one.
export const REASON_LABELS: Record<string, string> = {
  ai_unavailable: "AI check failed",
  photo_blurred: "Blurred photo",
  photo_dark: "Dark photo",
  stamp_missing: "No stamp found",
  signature_missing: "No signature found",
  lr_missing: "No LR number found",
  quantity_missing: "No quantity found",
  date_missing: "No date found",
  retake_cap_reached: "Two retakes used",
  lr_mismatch: "Wrong LR number",
  location_far: "Taken far from the consignee",
  date_mismatch: "Date doesn't match",
  shortage_remark: "Shortage remark",
  damage_remark: "Damage remark",
  other_remark: "Other remark",
  qty_short: "Quantity short",
  qty_mismatch: "Quantity doesn't match",
  low_confidence: "AI unsure",
};

export const FIELD_LABELS: Record<PodFieldName, string> = {
  lr_number: "LR number",
  consignee_stamp: "Consignee stamp",
  quantity_received: "Quantity received",
  remarks: "Remark",
  delivery_date: "Date on the paper",
  signature: "Signature",
};

// The same line decide() draws: below this, the field needs a person's eye.
export const MIN_CONFIDENCE = 0.8;
