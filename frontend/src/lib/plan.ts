// The `agrisense_plan` structured payload — frontend-defined schema, backend fills it.
// It rides INSIDE the frozen SSE contract as a fenced ```agrisense-plan block in a
// message's content, so no contract change is needed. planParse() extracts it.

export type Level = "low" | "medium" | "high";

export interface CropOption {
  name: string;
  suitability: number; // 0–100
  water: Level;
  risk: Level;
  netProfit: number; // BDT, rough estimate
}

export type StepKind =
  | "prep"
  | "sow"
  | "fertilizer"
  | "irrigation"
  | "pest"
  | "harvest";

export interface CalendarStep {
  date: string; // ISO or "Nov wk2"
  label: string;
  kind: StepKind;
}

export interface FinanceLine {
  label: string;
  amount: number; // BDT
}

export interface Citation {
  source: string;
  locator: string;
}

export interface AgriPlan {
  crop: string;
  location: string;
  farmSizeBigha: number;
  season: string;
  crops: CropOption[];
  calendar: CalendarStep[];
  finance: {
    costs: FinanceLine[];
    yieldKg: number;
    pricePerKg: number;
  };
  citations?: Citation[];
}

const FENCE = /```agrisense-plan\s*([\s\S]*?)```/;

/** Extract the plan (if any) from a message's content, plus the content with the
 *  fenced block stripped for display. Falls back to {plan:null} if absent/invalid. */
export function planParse(content: string): {
  plan: AgriPlan | null;
  display: string;
} {
  const m = content.match(FENCE);
  if (!m) return { plan: null, display: content };
  let plan: AgriPlan | null = null;
  try {
    plan = JSON.parse(m[1]) as AgriPlan;
  } catch {
    plan = null;
  }
  return { plan, display: content.replace(FENCE, "").trim() };
}

/** Serialize a plan into the fenced block (used by the mock agent + tests). */
export function planFence(plan: AgriPlan): string {
  return "```agrisense-plan\n" + JSON.stringify(plan) + "\n```";
}
