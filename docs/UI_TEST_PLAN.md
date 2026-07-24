# AgriSense — Web UI Test Plan

A manual QA script to exercise **every agent capability and edge case** through
the browser. Work top to bottom; each test says what to type/do and what a
**PASS** looks like. Check the **agent trace** (the "Thought for …" chip under a
reply) on every step — it exposes the tool calls, the params sent, and the raw
values returned, which is how you verify answers are *grounded*, not invented.

- Frontend: <http://localhost:3000> · Backend docs: <http://localhost:8080/docs>
- Bring the stack up: `docker compose up -d --build`
- If a UI change doesn't show, **hard-refresh** (Cmd/Ctrl+Shift+R).

## Real vs mock (so you know what's genuine)

| Genuinely live | Seeded / mock (clearly labelled in output) |
|---|---|
| Weather (Open-Meteo), CZIS crop/soil/fertilizer, geocoding gazetteer, KB retrieval (FRG 2024), on-device disease model, Gemini voice transcription | Item costs & sale prices (finance), per-application irrigation cost, organic-equivalent quantities, supplier/price catalog |

---

## 0. Setup

### 0.1 Register two accounts
Registration needs: **username, phone, password ×2, and an address**
(division → district → upazila → union).

- **Account A — Rajshahi farmer** (needed for season plans, which are sourced
  for Rajshahi only): pick **Division = Rajshahi**, e.g. District *Rajshahi* →
  Upazila *Paba* → any union. Phone e.g. `01700000001`.
- **Account B — non-Rajshahi farmer** (for the region edge case): pick e.g.
  **Division = Dhaka**. Phone e.g. `01700000002`.

**PASS:** both register and land in the chat. Log in **by phone** (not email).

> Tip: keep the trace panel open the whole session.

---

## 1. Tier 0 — Conversational intake & missing-info handling

The six mandatory slots are **location, farm size, soil type, water
availability, budget, season**. Crop advice is HARD-GATED until all six exist.

| # | Type this (Account A) | PASS criteria |
|---|---|---|
|1.1| `I want to grow a crop this season` | Agent does NOT recommend yet; asks for the missing fields (1–2 at a time), not a giant list. |
|1.2| `My farm is 50 decimal, budget 40000 taka` | Saves size + budget (trace shows `update_farm_profile`); asks for the still-missing ones. |
|1.3| `Water from a shallow tubewell, this is the rabi season` | Saves water + season; may state the **survey-default soil** for your upazila and ask you to confirm it. |
|1.4| `Soil is loam` | Saves soil; then summarizes the full profile and confirms before advising. |
|1.5| **Edge — premature ask:** in a fresh chat with an incomplete farm, `Which crop is most profitable?` | Agent refuses to rank and asks for the missing slot(s) first (hard gate). |

**Watch the trace:** each stated fact → a `update_farm_profile` call with only
what you said (never guessed values).

---

## 2. Tier 0 — Live weather grounding

| # | Type this | PASS criteria |
|---|---|---|
|2.1| `What's the weather forecast for my farm this week?` | Trace shows `get_weather`; reply cites actual rain mm / temps from the returned days (16-day max). |
|2.2| `How much rain fell last week?` | Uses `past_days`; rows marked as recorded (past), cited as such. |
|2.3| **Edge — far future:** `What will the weather be in 30 days?` | Agent says forecast reaches only ~16 days; does NOT invent daily weather beyond that. |

---

## 3. Tier 0 — Crop recommendation (≥3 ranked candidates)

| # | Type this (Account A, profile complete) | PASS criteria |
|---|---|---|
|3.1| `Recommend crops for my farm` | Trace shows `rank_crop_candidates`; ≥3 candidates each with suitability, water need, risk reasons, and a rough profit — with score components visible. |
|3.2| `Why did you rank wheat there?` | Explanation names your inputs (soil, water, budget, live suitability/weather), not generic text. |
|3.3| **Edge — exclusion:** `I don't want to grow rice` | Rice drops out / is explained as excluded. |

---

## 4. Tier 0 — Season plan (dated calendar)

Focused crops: **Wheat, Mustard, Potato, Maize, Boro dhan** · Rajshahi · rabi.

| # | Type this (Account A) | PASS criteria |
|---|---|---|
|4.1| `I choose wheat. Give me the season plan.` | Routes to **planner**; `generate_season_plan` runs; dated calendar from land-prep → sowing → fertilizer → irrigation → weed/pest → harvest, plus an embedded financial projection. Dates/quantities come from tools, not prose. |
|4.2| `Give me a plan for potato starting 2026-11-05` | Honors the planting date (or shifts it with a stated weather reason). |
|4.3| **Edge — region:** log in as **Account B** (Dhaka), complete its profile, `Plan for wheat` | Returns `UNSUPPORTED_CALENDAR_REGION` — the agent explains the calendars are sourced for Rajshahi only. No invented calendar. |
|4.4| **Edge — unsupported crop:** `Make a season plan for dragon fruit` | `UNSUPPORTED_CROP`; lists the five supported crops. |
|4.5| **Edge — irrigation gate:** set water = "no irrigation / rainfed", then `Plan for boro dhan` | `IRRIGATION_REQUIRED` — high-water crop refused without assured irrigation. |

---

## 5. Tier 0 — Financial projection (internally consistent)

| # | Type this | PASS criteria |
|---|---|---|
|5.1| `Show the cost and profit for wheat` | Itemized cost, yield, revenue, net profit, ROI, two break-even values, budget fit, math checks. Seeded costs/price are **labelled** as demo values. |
|5.2| **Consistency:** `What if the sale price is 35 taka per kg?` | Numbers change coherently (revenue/profit/ROI shift, break-evens update). Change an input → outputs move. |
|5.3| `Use my own expected yield of 4 tons per hectare` | Yield source switches to farmer estimate; projection recomputes. |

---

## 6. Tier 0 — Knowledge base / RAG grounding

| # | Type this | PASS criteria |
|---|---|---|
|6.1| `How should I split urea for wheat?` | Trace shows `search_knowledge_base`; answer cites **FRG 2024** with page numbers; does not present KB text as the final dose (deterministic tools own numbers). |
|6.2| **Edge — no entry:** `What is the fertilizer schedule for dragon fruit?` (out of corpus) | Says the guide has no specific entry; invents no citation. |

---

## 7. Tier 0 — Explainability & visible trace

| # | Check | PASS criteria |
|---|---|---|
|7.1| Click the trace chip on any recommendation/plan | Every tool call is listed with the **params sent** and the **raw values returned**. |
|7.2| Any farmer-facing number | Traceable to a tool result or KB citation in the trace — never free-text invention. |

---

## 8. Multi-farm handling

| # | Type this (Account A) | PASS criteria |
|---|---|---|
|8.1| `I also have another plot in Naogaon` | Agent calls `list_farms` / offers to `create_farm`; does NOT overwrite the current farm's location. |
|8.2| After creating it, `Recommend crops here` | Treats the new farm as empty → collects all six fields for it before advising. |
|8.3| `Switch back to my first farm` | `select_farm`; advice again reflects farm 1's data. |

---

## 9. Language (Bengali / Banglish)

| # | Type this | PASS criteria |
|---|---|---|
|9.1| `আমার জমির জন্য আবহাওয়া কেমন?` | Replies in **Bengali**; still calls the real tools. |
|9.2| `amar mati balu, ki fosol lagabo?` (Banglish) | Replies in Bengali script. |
|9.3| Switch back to English mid-chat | Next reply is English (language follows the LAST message). |

---

## 10. Memory across sessions

| # | Do this | PASS criteria |
|---|---|---|
|10.1| `My name is Karim and I've been farming for 20 years.` | Acknowledged. |
|10.2| Start a **new chat** (same account), `What's my name?` | Recalls "Karim" (long-term pgvector memory + auto-extraction across sessions). |
|10.3| **Edge:** ask it to remember a one-off number ("remember 2+2=4") | It should NOT store trivia as durable memory (only durable personal facts). |

---

## 11. Tier 1 — Fertilizer & irrigation scheduler

| # | Type this (Account A, wheat context) | PASS criteria |
|---|---|---|
|11.1| `Give me the fertilizer and irrigation schedule with cost for wheat` | Trace shows `generate_input_schedule`; per-growth-stage chemical quantities + **seeded** cost, **organic alternatives** (flagged as IPNS approximations), and an irrigation **water balance** (requirement − rainfall → applications + cost). |
|11.2| `What organic alternative can I use instead of urea?` | Gives organic-equivalent quantities with the transparent nutrient-equivalence basis; labelled approximate, "confirm via IPNS". |
|11.3| **Edge — no water requirement:** ask the same for **mustard** | Irrigation balance returns an explicit `unknown` (BAMIS doesn't publish it) — no invented figure. |

---

## 12. Tier 1 — Scenario simulation ("changed numbers, not generic")

| # | Type this | PASS criteria |
|---|---|---|
|12.1| `What if rainfall drops 30%?` | Trace shows `simulate_scenario`; returns **baseline vs revised** numbers with deltas — extra irrigation applications, added cost, and a yield-risk flag. |
|12.2| `What if my budget is cut 40%?` | Recomputes budget fit (new budget, surplus/gap) with explicit deltas — not a generic answer. |
|12.3| `What if the price falls 10% and costs rise 20%?` | Net profit / ROI drop coherently vs baseline. |

---

## 13. Tier 2 — Leaf-disease detection (image upload)

Model knows **potato, rice, tomato** only.

| # | Do this | PASS criteria |
|---|---|---|
|13.1| Click **📷**, upload a leaf photo, send (`what's wrong with this leaf?`) | The photo appears **in your chat bubble** (and stays after reload); trace shows `classify_leaf_disease`; reply relays the on-device diagnosis **label + confidence** and advises confirming with extension staff. |
|13.2| `This is a rice plant` + rice photo | Passing the crop hint reads the rice disease head. |
|13.3| **Edge — off-domain image:** upload a non-leaf photo | It still returns a class (low confidence) — the agent should present confidence honestly and recommend confirmation; it must not claim certainty. |
|13.4| **Edge:** send a photo with no text | Still diagnoses (default "check this leaf photo" prompt). |

**Regression to confirm:** after the turn finishes and after a page reload, the
uploaded image is **still visible** in the history (not just live).

---

## 14. Tier 2 — Voice notes (accessibility)

| # | Do this | PASS criteria |
|---|---|---|
|14.1| Click **🎤**, speak a question in Bengali, stop | A live recording timer shows; on stop, the **transcript** appears in the input box for review. |
|14.2| Send the transcript | Flows through the normal agent pipeline; reply in Bengali. |
|14.3| **Edge — silent/short clip** | Shows "No speech detected" (or a transcription-unavailable note) — never a fabricated transcript. |

---

## 15. Source-outage / fail-closed edge cases

These prove the agent **degrades honestly** and never invents data. You can
trigger them opportunistically (gov endpoints are genuinely flaky).

| # | Situation | PASS criteria |
|---|---|---|
|15.1| CZIS fertilizer endpoint down during a season plan | Plan comes back `status: degraded` with `fertilizer` unavailable; no invented fertilizer amounts. |
|15.2| Weather API unreachable | `WEATHER_UNAVAILABLE`; the agent says live weather is unavailable rather than inventing a forecast. |
|15.3| Disease model file missing | `DISEASE_MODEL_UNAVAILABLE`; no guessed diagnosis. |

---

## 16. Security / isolation spot-checks

| # | Do this | PASS criteria |
|---|---|---|
|16.1| Log in as **Account B**, try to open Account A's chat/session | 404 / not found — sessions are user-scoped. |
|16.2| Account B references Account A's uploaded image id | Not accessible — attachments are user-scoped. |

---

## Proactive weather SMS (NOT in this build)

The daily weather-triggered SMS lives on the `feat/proactive_weather_sms`
branch and is **not deployed here**. To test it, deploy that branch and use:
- `POST /api/alerts/scan-now` (with a Bearer token) → returns the scan report.
- `GET /api/alerts` → the farmer's alert history.
- In chat: `Any weather alerts for my farm?` → relays stored advisories.
SMS sends via sms.net.bd only when `SMS_DRY_RUN=false`; it messages only farms
whose forecast crosses a severe threshold (heavy rain ≥50 mm, heat ≥40 °C, cold
≤8 °C, or plan-aware fertilizer-delay / skip-irrigation), deduplicated.

---

## Quick pass/fail summary

Copy this checklist for a demo dry-run:

- [ ] Intake collects 6 fields, gates advice until complete
- [ ] Weather grounded in real Open-Meteo values
- [ ] ≥3 ranked crops with explained scores
- [ ] Dated season plan for a Rajshahi rabi crop
- [ ] Finance is internally consistent (change input → outputs change)
- [ ] KB answers cite FRG 2024 pages
- [ ] Trace shows every tool call + params + raw results
- [ ] Multi-farm switching keeps farms separate
- [ ] Bengali/Banglish replies
- [ ] Memory recalls a fact in a new session
- [ ] Scheduler: staged fertilizer + cost + organic + water balance
- [ ] Scenario: baseline vs revised numbers with deltas
- [ ] Leaf photo → diagnosis + confidence, image shown in thread (live + reload)
- [ ] Voice note → transcript → answer
- [ ] Outages degrade honestly (no invented numbers)
