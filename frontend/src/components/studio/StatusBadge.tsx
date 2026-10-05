import { Badge, type BadgeTone } from "@/components/ui/primitives";
import type { StudioStatus } from "@/lib/studio-api";

/**
 * One place that maps a workflow state to how it looks and reads.
 *
 * Six states now exist where the old admin knew three, so an ad-hoc ternary per
 * screen would show "in_review" raw in some places and nothing at all in others.
 */
const STATES: Record<StudioStatus, { label: string; tone: BadgeTone }> = {
  draft: { label: "Draft", tone: "slate" },
  in_review: { label: "In review", tone: "amber" },
  approved: { label: "Approved", tone: "purple" },
  scheduled: { label: "Scheduled", tone: "blue" },
  published: { label: "Public", tone: "green" },
  archived: { label: "Hidden", tone: "red" },
};

export function StatusBadge({ status }: { status: StudioStatus }) {
  const state = STATES[status] ?? { label: status, tone: "slate" as BadgeTone };
  return <Badge tone={state.tone}>{state.label}</Badge>;
}

export const STATUS_OPTIONS = (
  Object.keys(STATES) as StudioStatus[]
).map((value) => ({ value, label: STATES[value].label }));
