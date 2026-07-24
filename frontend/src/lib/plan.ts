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
// eslint-disable-next-line no-control-regex
const CONTROL_CHARS = /[\x00-\x08\x0B\x0C\x0E-\x1F]/g;
const TOOL_LINE = /^[ \t]*\[tool\b[^\]\n]*\][ \t]*\^?C?[ \t]*$/gim;
const TOOL_INLINE = /\[tool\b[^\]\n]*\]\s*\^?C?/gi;

/** Clean assistant text for display: strip control chars and inline tool-call
 *  narration (`[tool NAME args=… -> …]`) that weaker models sometimes emit as prose
 *  — the real, structured trace lives in the Agent Trace panel. */
export function cleanContent(text: string): string {
  return (text || "")
    .replace(CONTROL_CHARS, "")
    .replace(TOOL_LINE, "")
    .replace(TOOL_INLINE, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** Extract the plan (if any) from a message's content, plus cleaned display text
 *  (fenced plan block + tool narration stripped). {plan:null} if absent/invalid. */
export function planParse(content: string): {
  plan: AgriPlan | null;
  display: string;
} {
  const m = content.match(FENCE);
  let plan: AgriPlan | null = null;
  if (m) {
    try {
      plan = JSON.parse(m[1]) as AgriPlan;
    } catch {
      plan = null;
    }
  }
  const withoutPlan = m ? content.replace(FENCE, "") : content;
  return { plan, display: cleanContent(withoutPlan) };
}

/** Serialize a plan into the fenced block (used by the mock agent + tests). */
export function planFence(plan: AgriPlan): string {
  return "```agrisense-plan\n" + JSON.stringify(plan) + "\n```";
}
