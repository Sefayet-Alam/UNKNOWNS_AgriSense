// Mock SSE agent — emits the SAME StreamFrame shapes the real backend sends
// (session · message · progress · message_update · done), so the whole workspace
// runs and demos with zero backend. Swapped for the live stream in M5.
// STUB: not the real agent; scripted happy-paths (season plan + leaf diagnosis).

import { financeOf } from "./finance";
import { type AgriPlan, planFence } from "./plan";
import type { Message, StreamFrame } from "./types";

const DEMO_PLAN: AgriPlan = {
  crop: "Wheat",
  location: "Tanore, Rajshahi",
  farmSizeBigha: 2,
  season: "Rabi",
  crops: [
    { name: "Wheat", suitability: 88, water: "low", risk: "low", netProfit: 8200 },
    { name: "Potato", suitability: 74, water: "high", risk: "medium", netProfit: 12400 },
    { name: "Mustard", suitability: 61, water: "low", risk: "low", netProfit: 4900 },
  ],
  calendar: [
    { date: "Nov wk2", label: "Land preparation", kind: "prep" },
    { date: "Nov wk3", label: "Sowing window", kind: "sow" },
    { date: "Dec wk2", label: "Urea top-dress #1", kind: "fertilizer" },
    { date: "Jan wk1", label: "Irrigation (weather-aware)", kind: "irrigation" },
    { date: "Jan wk3", label: "Pest & disease check", kind: "pest" },
    { date: "Feb wk4", label: "Harvest", kind: "harvest" },
  ],
  finance: {
    costs: [
      { label: "Seed", amount: 1200 },
      { label: "Fertilizer", amount: 3400 },
      { label: "Irrigation", amount: 2100 },
      { label: "Labour", amount: 4600 },
    ],
    yieldKg: 720,
    pricePerKg: 38,
  },
  citations: [
    { source: "FRG 2024", locator: "p.87" },
    { source: "CZIS suitability", locator: "upz 508194" },
  ],
};

const now = () => new Date().toISOString();

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

export interface MockAttachment {
  kind: "image" | "document";
  name: string;
}

export interface MockTurnArgs {
  userText: string;
  onEvent: (frame: StreamFrame) => void;
  signal?: AbortSignal;
  sessionId?: number;
  attachment?: MockAttachment;
}

const MODEL = "claude-sonnet-5";

/** Play one scripted turn, emitting live-shaped frames over time. */
export async function runMockTurn({
  userText,
  onEvent,
  signal,
  sessionId = 1,
  attachment,
}: MockTurnArgs): Promise<void> {
  try {
    onEvent({ type: "session", session_id: sessionId });

    const userMsg: Message = {
      id: Date.now(),
      role: "user",
      content: userText,
      tool_trace: [],
      model: "",
      created_at: now(),
    };
    onEvent({ type: "message", message: userMsg });

    if (attachment?.kind === "image") {
      await runLeafDiagnosis({ attachment, onEvent, signal });
    } else {
      await runSeasonPlan({ onEvent, signal });
    }

    await sleep(200, signal);
    onEvent({ type: "done" });
  } catch (err) {
    if ((err as DOMException)?.name === "AbortError") return;
    onEvent({ type: "error", detail: "Mock agent failed.", session_id: sessionId });
  }
}

async function runSeasonPlan({
  onEvent,
  signal,
}: {
  onEvent: (f: StreamFrame) => void;
  signal?: AbortSignal;
}) {
  await sleep(450, signal);
  onEvent({ type: "progress", stage: "thinking", detail: "reading your farm profile" });

  await sleep(650, signal);
  onEvent({ type: "progress", stage: "tool", detail: "calling get_weather for Tanore" });

  const aId = Date.now() + 1;
  const msg: Message = {
    id: aId,
    role: "assistant",
    content: "",
    tool_trace: [
      { tool: "get_weather", args: { lat: 24.62, lon: 88.53, upazila: "508194" }, result: "" },
    ],
    model: MODEL,
    created_at: now(),
  };
  onEvent({ type: "message", message: msg });

  await sleep(850, signal);
  msg.tool_trace[0].result =
    '{"temp_c":14,"rain_mm_7d":2,"humidity":61,"source":"open-meteo"}';
  onEvent({ type: "message_update", message: { ...msg } });

  await sleep(450, signal);
  onEvent({ type: "progress", stage: "tool", detail: "searching knowledge base (FRG 2024)" });
  await sleep(750, signal);
  msg.tool_trace = [
    ...msg.tool_trace,
    {
      tool: "search_kb",
      args: { query: "wheat fertilizer sandy soil rabi", top_k: 4 },
      result:
        '[{"source":"FRG 2024","page":87,"snippet":"Wheat, sandy loam: urea 220 kg/ha split..."}]',
    },
  ];
  onEvent({ type: "message_update", message: { ...msg } });

  await sleep(400, signal);
  onEvent({ type: "progress", stage: "tool", detail: "ranking suitable crops" });
  await sleep(700, signal);
  msg.tool_trace = [
    ...msg.tool_trace,
    {
      tool: "rank_crops",
      args: { upazila: "508194", season: "Rabi", water: "canal", budget: 15000 },
      result: '[{"crop":"Wheat","suit":88},{"crop":"Potato","suit":74},{"crop":"Mustard","suit":61}]',
    },
  ];
  onEvent({ type: "message_update", message: { ...msg } });

  await sleep(500, signal);
  onEvent({ type: "progress", stage: "thinking", detail: "costing the season plan" });
  await sleep(800, signal);
  const fin = financeOf(DEMO_PLAN);
  msg.content =
    `Based on Tanore's cool, dry Rabi window (14°C, ~2 mm rain forecast this week) and your ` +
    `sandy soil with canal water, **Wheat** is the best fit for 2 bigha — low water need, low risk, ` +
    `and a projected net profit of **৳${fin.netProfit.toLocaleString("en-IN")}** (ROI ${fin.roiPct}%). ` +
    `Potato pays more but needs far more water and carries higher risk on sandy soil.\n\n` +
    planFence(DEMO_PLAN);
  onEvent({ type: "message_update", message: { ...msg } });
}

async function runLeafDiagnosis({
  attachment,
  onEvent,
  signal,
}: {
  attachment: MockAttachment;
  onEvent: (f: StreamFrame) => void;
  signal?: AbortSignal;
}) {
  await sleep(500, signal);
  onEvent({ type: "progress", stage: "thinking", detail: `analyzing ${attachment.name}` });

  await sleep(700, signal);
  onEvent({ type: "progress", stage: "tool", detail: "calling diagnose_leaf (vision)" });

  const aId = Date.now() + 1;
  const msg: Message = {
    id: aId,
    role: "assistant",
    content: "",
    tool_trace: [{ tool: "diagnose_leaf", args: { image: attachment.name }, result: "" }],
    model: MODEL,
    created_at: now(),
  };
  onEvent({ type: "message", message: msg });

  await sleep(1000, signal);
  msg.tool_trace[0].result =
    '{"disease":"Early blight (Alternaria solani)","confidence":0.86,"severity":"moderate","crop":"tomato"}';
  onEvent({ type: "message_update", message: { ...msg } });

  await sleep(450, signal);
  onEvent({ type: "progress", stage: "tool", detail: "searching treatment guidance" });
  await sleep(750, signal);
  msg.tool_trace = [
    ...msg.tool_trace,
    {
      tool: "search_kb",
      args: { query: "early blight tomato treatment", top_k: 3 },
      result:
        '[{"source":"DAE Pest Guide","page":42,"snippet":"Alternaria: remove affected leaves; mancozeb 2 g/L..."}]',
    },
  ];
  onEvent({ type: "message_update", message: { ...msg } });

  await sleep(500, signal);
  onEvent({ type: "progress", stage: "thinking", detail: "preparing treatment plan" });
  await sleep(800, signal);
  msg.content =
    `That looks like **Early blight (Alternaria solani)** — moderate severity, ~86% confidence. ` +
    `It's the concentric brown "target" spots on the lower, older leaves.\n\n` +
    `**Do this now:** remove and burn affected leaves; avoid overhead watering; spray **Mancozeb 2 g/L** ` +
    `every 7–10 days (2–3 rounds). Mulch to stop soil splash, and rotate away from tomato/potato next season.\n\n` +
    `_Grounded in: DAE Pest Guide, p.42_`;
  onEvent({ type: "message_update", message: { ...msg } });
}

export const DEMO_OPENER =
  "I want to plant something this winter. 2 bigha in Tanore, sandy soil, canal water, budget about 15000 taka.";
