# UNKNOWNS AgriSense

**Team UNKNOWNS:** 
1. Khandoker Sefayet Alam (Team Lead)
2. Nazib Abrar, 
3. Md. Raihanul Haque Rahi
**Institution:** Rajshahi University of Engineering & Technology (RUET)
**Live:** [https://agrisense.cortextech.dev](https://agrisense.cortextech.dev)

## Setup

```bash
cp .env.example .env
# Set JWT_SECRET_KEY and OPENROUTER_API_KEY in .env
docker compose up --build
```

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8080`
- API docs: `http://localhost:8080/docs`

## Tier 0: Core

| Task | How it is implemented | Data status and source |
|---|---|---|
| Agent model and multi-step reasoning | LangGraph routes each turn through intake, advisor, recommender, planner, or finance specialists. The primary agent model is configured by `OPENROUTER_MODEL`, default `google/gemini-2.5-flash`; intent classification and extraction use `OPENROUTER_MODEL_LITE`, default `google/gemini-2.5-flash-lite`. A request is limited to six live tool rounds. | LLM output is generated. Tool-derived facts are separated from model text. |
| Conversational intake and memory | The active farm persists location, farm size, soil type, water availability, budget, and season. The agent asks only for missing fields. Incomplete recommendation, plan, and finance requests are deterministically routed back to intake. Farm profiles, session summaries, and semantic long-term memory persist across chats. | Farmer-provided data is real user input. Soil can be an upazila-level public-survey default and is marked for farmer confirmation. |
| Live weather grounding | `get_weather` resolves the active farm coordinates and retrieves forecast or recent historical weather. Returned rainfall, temperature, wind, ET0, and forecast dates are used in advice. | Real live Open-Meteo API data. Failure returns `WEATHER_UNAVAILABLE`; no forecast is invented. |
| Crop recommendation | `rank_crop_candidates` combines farm profile, BARC CZIS point suitability, water fit, budget fit, forecast risk, local cropping-pattern economics, and finance assumptions. It returns at least three eligible candidates with suitability, water need, risk, and rough profit. | CZIS suitability is real live data when available. Cropping patterns and soil are bundled public-data snapshots. Rough crop costs and sale prices are seeded demo assumptions unless the farmer supplies overrides. |
| Crop varieties and fertilizer | The agent retrieves CZIS varieties and farm-scaled fertilizer recommendations for the active farm coordinates. | Real live BARC CZIS data when available. Outages are surfaced as structured unavailable results. |
| Dated season plan | `generate_season_plan` produces land preparation, sowing, fertilizer, irrigation, weed, pest, and harvest events for a selected crop. | BAMIS crop-weather calendars and BARC FRG 2024 are public reference data. Live weather and CZIS fertilizer results are added when available. Sourced dated calendars currently cover wheat, mustard, potato, maize, and Boro dhan. |
| Financial projection | A server-side Decimal engine calculates itemized cost, expected yield, revenue, net profit, ROI, break-even yield, and break-even price. Changing area, yield, sale price, or cost inputs recomputes the output. | Arithmetic is deterministic. Yield comes from CZIS variety data or a farmer estimate. Default costs and prices come from the 67-crop seeded finance-assumptions catalog and are labelled as demo values. |
| RAG knowledge base | FRG 2024 and curated agronomy notes are recursively split with `RecursiveCharacterTextSplitter` using 1,800-character chunks, 200-character overlap, and paragraph, line, sentence, word separators. Page ranges are retained. Retrieval uses pgvector, top 3 matches, and a 0.35 similarity floor. The embedding model is `openai/text-embedding-3-small` through OpenRouter by default, 1,536 dimensions. | FRG 2024, BAMIS, and curated extension material are public reference data. Retrieved passages are treated as untrusted reference text; final fertilizer quantities come from deterministic CZIS tools. |
| Visible agent trace and explainability | Streaming chat stores and displays each tool name, arguments, raw result, and progress event. Responses name the farm inputs and retrieved evidence behind recommendations. | Trace values are the actual returned tool payloads. |

## Tier 1: Advanced

| Task | How it is implemented | Data status and source |
|---|---|---|
| Persistent memory | Farm profiles, chat sessions, rolling summaries, and semantic long-term memory are stored in PostgreSQL and pgvector. | Farmer-provided profile and preference data. |
| Proactive weather alerts | A background weather scan evaluates saved plans against forecast conditions, persists alerts, and exposes them to the agent. | Real Open-Meteo forecast data when available. |
| Fertilizer and irrigation scheduler | `generate_input_schedule` creates growth-stage fertilizer timing, farm-scaled quantities, irrigation water balance, cost, and organic alternatives. | CZIS fertilizer data and BAMIS/FRG public references. Organic nutrient equivalents and retail costs are labelled assumptions. |
| Scenario simulation | `simulate_scenario` recomputes baseline and revised financial, budget, irrigation, and yield-risk outputs for rainfall, budget, cost, price, or yield changes. | Deterministic computation. Base inputs retain their original CZIS, farmer, public-reference, or seeded-demo provenance. |
| Leaf disease detection | Uploaded leaf images are classified by an on-device quantized TFLite model; the agent returns its label, confidence, and alternatives. | Local model inference. The result is a model prediction, not laboratory confirmation. |
| Bengali accessibility | Bengali-script messages receive Bengali replies. Banglish is detected and answered in Bengali script. | Generated language output grounded in the same tool results. |

## Tier 2: Bonus

| Task | How it is implemented | Data status and source |
|---|---|---|
| Supplier marketplace | `find_suppliers` ranks suppliers by price, delivery time, distance, and rating for an input requirement. | Supplier prices, delivery, and ratings are seeded demo data. Distance is calculated from active-farm coordinates. |
| Market-price intelligence | `get_market_price` returns price history, trend, volatility, and a sell-now, store, or wait decision. | Historical snapshot is seeded from typical DAM/TCB-level data. A configured live price adapter is best-effort and explicitly reports unavailability. |
| BDApps payment | The billing UI and API implement a BDApps CaaS-compatible checkout, operator-balance deduction, and receipt flow. | Local sandbox/simulator by default. No carrier charge occurs in sandbox mode. |
