import type { EquipmentType } from "../types";

export const EQUIPMENT_TYPE_OPTIONS: { value: EquipmentType; label: string }[] = [
  { value: "tent", label: "Tent" },
  { value: "rv", label: "RV" },
  { value: "trailer", label: "Trailer" },
  { value: "vehicle", label: "Vehicle" },
  { value: "horse", label: "Horse camping" },
];

export const EQUIPMENT_TYPE_LABELS: Record<EquipmentType, string> = EQUIPMENT_TYPE_OPTIONS.reduce(
  (acc, { value, label }) => ({ ...acc, [value]: label }),
  {} as Record<EquipmentType, string>,
);
