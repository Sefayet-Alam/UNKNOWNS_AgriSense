I read the complete seven-page problem statement and inspected the structure of the three proposed data sources. The most important conclusion is:

> **Do not build this as one general-purpose chatbot with three scraping tools. Build it as a bounded agricultural planning workflow in which the LLM gathers information and explains results, while deterministic services perform crop ranking, fertilizer calculation, scheduling, and financial arithmetic.**

The brief rewards a complete chain of dependent decisions, targeted handling of missing data, persistent memory, real tool use, and recommendations that explicitly name their supporting inputs. 

---

# 1. What the three sources should actually do

Your proposed source allocation needs one important correction.

| Source                                    | Correct role                                                                                     | Should it be ordinary RAG?                                                |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------- |
| BARC Fertilizer Recommendation Guide 2024 | Fertilizer rules, nutrient rates, soil-test interpretation, application principles               | **Hybrid:** RAG for explanation, structured tables/rules for calculations |
| CZIS Crop Zoning                          | Location-specific land, soil, AEZ, suitability, cropping pattern and possibly fertilizer context | Primarily structured/geospatial retrieval                                 |
| BAMIS crop weather calendar               | Crop stages, regional calendars, weather requirements and weather-sensitive risks                | Structured calendar/rule extraction, supplemented by RAG                  |
| Live weather API                          | Current and upcoming rainfall, temperature, humidity, wind, ET₀ and soil conditions              | Direct tool call                                                          |
| Market/cost source                        | Price and cost assumptions used in financial projection                                          | Structured retrieval                                                      |

## Critical nuance 1: FRG is not merely a RAG document

The BARC guide explicitly says its recommendations are **not blanket recommendations**. It defines two major paths:

1. When site-specific soil-test values are unavailable, use recommendations based on cropping patterns and Agro-Ecological Zones.
2. When soil-test values are available, classify the soil into fertility categories and develop a location-specific recommendation using the relevant tables and appendices. ([BARC Apps][1])

Therefore, this would be unsafe:

```text
Question → vector search FRG → LLM invents fertilizer quantity
```

The correct design is:

```text
FRG PDF
   ├── document chunks → vector search → explanations and citations
   └── validated tables → relational database → deterministic calculator
```

The model should never read three retrieved paragraphs and calculate an authoritative fertilizer dose itself.

## Critical nuance 2: BAMIS is not the primary crop-recommendation engine

BAMIS lists crop-specific calendars for crops such as potato, mustard, wheat, maize, Boro rice, Aman rice, lentil and others, and then offers regional calendars such as Rajshahi for individual crops. ([Bamis][2])

But BAMIS mainly answers:

* When is this crop normally grown?
* What are its stage-specific weather requirements?
* What weather conditions increase risk?
* Does the current forecast fit the crop calendar?

It does **not primarily answer**:

> “Of every available crop, which three are best for this exact parcel?”

That candidate generation should come from CZIS.

## Critical nuance 3: CZIS should generate the candidate crops

CZIS exposes crop suitability analysis, existing and profitable cropping patterns, crop zoning, crop varieties, union-based fertilizer recommendations, point-based fertilizer recommendations and layers such as land type, soil polygon, growing period, AEZ and flood-prone area. ([czis.cropzoning.gov.bd][3])

CZIS describes its suitability analysis as combining:

* soil and land or edaphic factors;
* agro-climatic factors;
* inundation;
* economics.

It uses an upazila land and soil resources database at approximately 1:50,000 scale. ([portal.cropzoning.gov.bd][4])

The older BARC crop-zoning system explains that suitability considers soil properties such as drainage, depth, pH, salinity, moisture and nutrient status, together with climatic growing-period and temperature constraints. It maps suitability to approximate attainable-yield classes. ([BARC Apps][5])

## Critical nuance 4: `upz=508194` is Tanore, but that is not enough

The code `508194` corresponds to **Tanore Upazila, Rajshahi**. ([Oracle Cloud][6])

However, an upazila can contain several:

* unions;
* soil polygons;
* land types;
* drainage conditions;
* flood conditions;
* fertility levels.

Therefore, the farmer should ideally provide:

```text
GPS point or map pin
    ↓
Union
    ↓
Soil polygon / land type / AEZ
    ↓
Specific suitability and fertilizer context
```

When only the upazila is known, the system should return a lower-confidence upazila-level recommendation rather than pretending it knows the parcel.

---

# 2. The correct hackathon scope

The brief explicitly says to build one complete end-to-end core before adding advanced features. Tier 0 requires conversational intake, live weather, three crop recommendations, a dated season plan, financial calculations, explained recommendations, RAG and a visible tool trace. 

For 24 hours, I recommend this vertical slice:

```text
Location:
    Tanore, Rajshahi

Primary season:
    Rabi

Initially supported crops:
    Potato
    Mustard
    Wheat
    Rabi maize
    Optionally Boro rice

Input units:
    Decimal
    Bigha
    Acre
    Hectare

Output:
    Top 3 crops
    Selected-crop season plan
    Fertilizer schedule
    Irrigation checkpoints
    Pest/weather warnings
    Cost/profit projection
    Visible evidence trace
```

Do not normalize every crop in the 200-plus-page fertilizer guide during the hackathon. Normalize and manually verify the tables for four or five demo crops.

The brief specifically warns that a complete core is more valuable than several unfinished features, and that judges will notice when retrieved weather is not actually used in recommendations. 

---

# 3. Proposed architecture

```text
                         ┌─────────────────────────┐
                         │ Farmer web/mobile chat  │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │ FastAPI authenticated   │
                         │ conversation endpoint   │
                         └────────────┬────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────┐
                    │ LangGraph bounded workflow       │
                    │                                  │
                    │ 1. Extract profile updates       │
                    │ 2. Ask for missing fields        │
                    │ 3. Retrieve land context         │
                    │ 4. Fetch weather                 │
                    │ 5. Rank candidate crops          │
                    │ 6. Farmer selects crop           │
                    │ 7. Build complete season plan    │
                    │ 8. Validate and explain          │
                    └─────────┬───────────┬────────────┘
                              │           │
                  ┌───────────┘           └────────────┐
                  ▼                                    ▼
        ┌───────────────────┐                ┌──────────────────────┐
        │ Structured engines│                │ Knowledge retrieval  │
        │                   │                │                      │
        │ Crop scorer       │                │ FRG vector index     │
        │ Fertilizer engine │                │ BAMIS knowledge      │
        │ Calendar builder  │                │ Agronomic documents │
        │ Finance engine    │                └──────────────────────┘
        │ Risk engine       │
        └─────────┬─────────┘
                  │
                  ▼
        ┌────────────────────────────────────────────┐
        │ Data adapters                              │
        │ CZIS | BAMIS | Open-Meteo | DAM | Postgres│
        └────────────────────────────────────────────┘
```

## Why a custom `StateGraph` rather than one free-form agent

LangGraph distinguishes predetermined workflows from dynamic agents. Your process has a required sequence and regulatory-like numerical rules, so the outer system should be a workflow, not an unconstrained agent. ([Docs by LangChain][7])

Use:

* **Structured LLM output** to extract farmer information and classify conversational requests.
* **Deterministic conditional edges** for routing based on missing fields and workflow phase.
* **`Command`** when one node must update state and route simultaneously.
* **`Send`** to evaluate several crop candidates in parallel.
* **`interrupt()`** for crop selection, confirmation of assumptions and final-plan approval.

Current LangGraph guidance says `Command` is appropriate when combining state updates with routing, while `Send` supports dynamic map-reduce fan-out. ([Docs by LangChain][8])

---

# 4. Data model

```python
class RuntimeContext:
    # Obtained from authenticated FastAPI middleware.
    user_id: str
    organization_id: str | None
    request_id: str


class FarmProfile:
    farm_id: str
    user_id: str

    # Location
    location_text: str | None
    latitude: float | None
    longitude: float | None
    division: str | None
    district: str | None
    upazila: str | None
    upazila_code: str | None
    union: str | None
    ae_zone: str | None

    # Farm characteristics
    area_hectare: Decimal | None
    original_area_value: Decimal | None
    original_area_unit: str | None
    land_type: str | None
    soil_texture: str | None
    drainage: str | None
    flood_risk: str | None
    previous_crop: str | None

    # Optional real soil test
    soil_test_date: date | None
    soil_ph: float | None
    organic_matter_pct: float | None
    nitrogen_value: float | None
    phosphorus_value: float | None
    potassium_value: float | None
    sulphur_value: float | None
    zinc_value: float | None
    boron_value: float | None
    soil_test_method: str | None

    # Farmer constraints
    season: str | None
    desired_sowing_window: DateRange | None
    irrigation_available: bool | None
    water_source: str | None
    irrigation_capacity: str | None
    budget_bdt: Decimal | None
    risk_tolerance: Literal["low", "medium", "high"] | None
    preferred_crops: list[str]
    excluded_crops: list[str]
    labour_constraints: str | None
    storage_available: bool | None


class EvidenceRecord:
    evidence_id: str
    source_name: str
    source_type: Literal[
        "czis",
        "barc_frg",
        "bamis",
        "weather",
        "market",
        "farmer_input",
        "system_assumption",
    ]

    source_reference: str
    source_version: str | None
    fetched_at: datetime
    request_parameters: dict
    normalized_values: dict
    units: dict
    raw_payload_storage_key: str | None
    raw_payload_hash: str | None
    confidence: float
    warnings: list[str]


class CropEvaluation:
    crop_id: str
    crop_name: str
    variety_options: list[str]

    czis_suitability_class: str
    czis_suitability_score: float

    season_fit_score: float
    forecast_fit_score: float
    water_feasibility_score: float
    budget_feasibility_score: float
    economic_score: float
    rotation_score: float

    total_score: float
    expected_yield_low: Decimal
    expected_yield_base: Decimal
    expected_yield_high: Decimal

    expected_cost: Decimal
    expected_revenue_low: Decimal
    expected_revenue_base: Decimal
    expected_revenue_high: Decimal

    risk_level: str
    limiting_factors: list[str]
    supporting_evidence_ids: list[str]


class SeasonTask:
    task_id: str
    category: Literal[
        "land_preparation",
        "sowing",
        "fertilizer",
        "irrigation",
        "weed",
        "pest_scouting",
        "disease_scouting",
        "harvest",
        "marketing",
    ]

    stage: str
    planned_start: date
    planned_end: date
    quantity: Decimal | None
    unit: str | None
    estimated_cost_bdt: Decimal
    weather_constraints: list[dict]
    prerequisites: list[str]
    reason_codes: list[str]
    evidence_ids: list[str]


class FinancialProjection:
    cost_items: list[CostItem]
    total_variable_cost: Decimal
    total_fixed_cost: Decimal
    total_cost: Decimal

    yield_low: Decimal
    yield_base: Decimal
    yield_high: Decimal

    selling_price_low: Decimal
    selling_price_base: Decimal
    selling_price_high: Decimal

    revenue_low: Decimal
    revenue_base: Decimal
    revenue_high: Decimal

    net_profit_low: Decimal
    net_profit_base: Decimal
    net_profit_high: Decimal

    roi_low_pct: Decimal
    roi_base_pct: Decimal
    roi_high_pct: Decimal

    break_even_yield: Decimal
    break_even_price: Decimal
    assumptions: list[str]


class AgriSenseState:
    messages: list
    phase: Literal[
        "intake",
        "land_resolution",
        "candidate_generation",
        "crop_selection",
        "plan_generation",
        "plan_review",
        "active_season",
        "completed",
    ]

    farm_profile: FarmProfile
    missing_fields: list[str]
    validation_errors: list[str]

    land_context: dict | None
    weather_snapshot: dict | None
    candidate_crop_ids: list[str]
    crop_evaluations: list[CropEvaluation]
    selected_crop: CropEvaluation | None

    fertilizer_plan: list[SeasonTask]
    irrigation_plan: list[SeasonTask]
    season_plan: list[SeasonTask]
    financial_projection: FinancialProjection | None

    evidence_ledger: list[EvidenceRecord]
    assumptions: list[str]
    warnings: list[str]
    confidence: float

    pending_human_action: dict | None
    plan_version: int
```

---

# 5. Offline data-ingestion pipeline

This must be prepared before the demo.

## 5.1 BARC FRG ingestion

```python
async def ingest_frg_2024(pdf_path):
    document_version = sha256(pdf_path)

    pages = extract_pages_preserving_page_numbers(pdf_path)
    table_candidates = detect_tables(pages)

    # A. Document retrieval collection
    chunks = []

    for section in split_by_heading_and_crop(pages):
        chunks.append(
            KnowledgeChunk(
                text=section.text,
                metadata={
                    "source": "BARC FRG 2024",
                    "document_version": document_version,
                    "page_start": section.page_start,
                    "page_end": section.page_end,
                    "crop": section.crop,
                    "topic": section.topic,
                    "land_environment": section.land_environment,
                },
            )
        )

    vector_store.upsert(chunks)

    # B. Structured fertilizer rules
    for table in table_candidates:
        if not table_is_relevant_to_supported_crop(table):
            continue

        parsed_rows = parse_fertilizer_table(table)

        # Mandatory manual verification for hackathon-supported crops.
        reviewed_rows = human_verify_against_rendered_pdf(
            parsed_rows,
            original_page_image=table.page_image,
        )

        for row in reviewed_rows:
            relational_db.upsert(
                FertilizerRule(
                    crop=row.crop,
                    variety_or_yield_goal=row.variety_or_yield_goal,
                    land_environment=row.land_environment,
                    soil_fertility_class=row.soil_fertility_class,
                    nutrient_name=row.nutrient,
                    recommended_nutrient_kg_per_hectare=row.rate,
                    basal_fraction=row.basal_fraction,
                    split_schedule=row.split_schedule,
                    source_page=row.page,
                    source_table=row.table_number,
                    document_version=document_version,
                )
            )

    run_integrity_tests()
```

### Required integrity tests

```python
def run_integrity_tests():
    assert no_duplicate_rule_keys()
    assert all_rates_are_non_negative()
    assert every_structured_row_has_page_reference()
    assert every_supported_crop_has_complete_required_nutrients()
    assert units_are_explicit()
    assert extracted_values_match_manually_recorded_golden_rows()
```

A vector-database answer must never override the structured table.

---

## 5.2 BAMIS ingestion

BAMIS currently exposes a crop list and regional calendar pages, including a Rajshahi calendar option for crops such as Boro rice. ([Bamis][2])

```python
async def ingest_bamis():
    crop_pages = crawl_calendar_index()

    for crop_page in crop_pages:
        crop = normalize_crop_name(crop_page.title)
        region_links = extract_region_links(crop_page)

        crop_requirements = parse_crop_requirements_page(crop)

        for region_link in region_links:
            region = normalize_region(region_link.name)
            calendar_file = download_calendar(region_link)

            parsed = parse_calendar_pdf_or_page(calendar_file)

            db.upsert(
                CropWeatherCalendar(
                    crop=crop,
                    region=region,
                    typical_duration_days=parsed.duration_days,
                    sowing_window=parsed.sowing_window,
                    stages=parsed.stages,
                    weekly_temperature_ranges=parsed.temperature_ranges,
                    weekly_rainfall_ranges=parsed.rainfall_ranges,
                    weekly_humidity_ranges=parsed.humidity_ranges,
                    sunshine_requirements=parsed.sunshine,
                    disease_weather_rules=parsed.disease_rules,
                    pest_weather_rules=parsed.pest_rules,
                    source_reference=region_link,
                    source_version=sha256(calendar_file),
                )
            )

        db.upsert(
            CropClimateRequirements(
                crop=crop,
                optimum_air_temperature=crop_requirements.air_temperature,
                optimum_soil_temperature=crop_requirements.soil_temperature,
                humidity_range=crop_requirements.humidity,
                rainfall_requirement=crop_requirements.rainfall,
                sunshine_requirement=crop_requirements.sunshine,
                salinity_sensitivity=crop_requirements.salinity,
                source_reference=crop_page,
            )
        )
```

For example, BAMIS states that mustard is a cool-season crop with specified temperature, soil-temperature, sunshine and humidity ranges, while potato has temperature-sensitive tuber formation and rainfall and soil-moisture requirements. ([Bamis][9])

These values should become structured constraints, not remain prose.

---

## 5.3 CZIS adapter

I could verify CZIS’s public functionality but did not find a documented public API specification. The page is a client-driven Web GIS interface. Therefore, do not couple your business logic directly to its HTML.

```python
class CZISAdapter(Protocol):
    async def resolve_land_context(
        self,
        upazila_code: str,
        latitude: float | None,
        longitude: float | None,
        union: str | None,
    ) -> LandContext:
        ...

    async def get_crop_suitability(
        self,
        location: LandContext,
        season: str,
    ) -> list[CropSuitability]:
        ...

    async def get_cropping_patterns(
        self,
        location: LandContext,
    ) -> list[CroppingPattern]:
        ...
```

Implementation priority:

```python
async def create_czis_adapter():
    if documented_or_authorized_json_endpoint_available():
        return CZISApiAdapter()

    if authorized_wms_or_wfs_service_available():
        return CZISGeospatialServiceAdapter()

    if permitted_browser_automation_is_stable():
        return CZISPlaywrightAdapter()

    return CachedOfficialSnapshotAdapter(
        snapshot="tanore_rabi_verified_snapshot.json",
        disclosure="Cached official CZIS data used",
    )
```

### Production warning

BARC’s map-download portal states that commercial use of downloaded maps and shapefiles is prohibited. A hackathon prototype and a future commercial service are different use cases; obtain written permission or licensing clarification before production ingestion. ([BARC Apps][10])

For the hackathon, your README should say exactly:

```text
CZIS data:
- Real source: BARC CZIS
- Retrieval mode: live endpoint / permitted browser extraction / cached official snapshot
- Snapshot date:
- Supported area: Tanore
- Not claimed: nationwide production-grade integration
```

The brief explicitly requires separating real data from generated or mocked data. 

---

# 6. LangGraph workflow

## 6.1 Graph construction

```python
builder = StateGraph(
    AgriSenseState,
    context_schema=RuntimeContext,
)

builder.add_node("load_farm_memory", load_farm_memory)
builder.add_node("extract_profile_updates", extract_profile_updates)
builder.add_node("validate_profile", validate_profile)
builder.add_node("ask_targeted_question", ask_targeted_question)

builder.add_node("resolve_location", resolve_location)
builder.add_node("fetch_land_context", fetch_land_context)
builder.add_node("fetch_weather", fetch_weather)
builder.add_node("generate_candidates", generate_candidates)

builder.add_node("evaluate_crop", evaluate_crop)
builder.add_node("rank_candidates", rank_candidates)
builder.add_node("present_candidates", present_candidates)
builder.add_node("select_crop", select_crop)

builder.add_node("retrieve_frg_context", retrieve_frg_context)
builder.add_node("calculate_fertilizer", calculate_fertilizer)
builder.add_node("build_crop_calendar", build_crop_calendar)
builder.add_node("calculate_irrigation", calculate_irrigation)
builder.add_node("calculate_risks", calculate_risks)
builder.add_node("fetch_market_and_costs", fetch_market_and_costs)
builder.add_node("calculate_financials", calculate_financials)

builder.add_node("merge_plan", merge_plan)
builder.add_node("validate_plan", validate_plan)
builder.add_node("review_plan", review_plan)
builder.add_node("persist_plan", persist_plan)
builder.add_node("render_answer", render_answer)

builder.add_edge(START, "load_farm_memory")
builder.add_edge("load_farm_memory", "extract_profile_updates")
builder.add_edge("extract_profile_updates", "validate_profile")

builder.add_conditional_edges(
    "validate_profile",
    route_after_profile_validation,
    {
        "missing": "ask_targeted_question",
        "ready": "resolve_location",
        "invalid": "ask_targeted_question",
    },
)

builder.add_edge("ask_targeted_question", END)

builder.add_edge("resolve_location", "fetch_land_context")
builder.add_edge("fetch_land_context", "fetch_weather")
builder.add_edge("fetch_weather", "generate_candidates")

# Send is returned from a conditional routing function.
builder.add_conditional_edges(
    "generate_candidates",
    fan_out_crop_evaluations,
)

builder.add_edge("evaluate_crop", "rank_candidates")
builder.add_edge("rank_candidates", "present_candidates")
builder.add_edge("present_candidates", "select_crop")

# After crop selection, independent work can proceed in parallel.
builder.add_edge("select_crop", "retrieve_frg_context")
builder.add_edge("select_crop", "build_crop_calendar")
builder.add_edge("select_crop", "fetch_market_and_costs")

builder.add_edge("retrieve_frg_context", "calculate_fertilizer")
builder.add_edge("build_crop_calendar", "calculate_irrigation")
builder.add_edge("build_crop_calendar", "calculate_risks")

builder.add_edge(
    [
        "calculate_fertilizer",
        "calculate_irrigation",
        "calculate_risks",
        "fetch_market_and_costs",
    ],
    "calculate_financials",
)

builder.add_edge("calculate_financials", "merge_plan")
builder.add_edge("merge_plan", "validate_plan")
builder.add_edge("validate_plan", "review_plan")
builder.add_edge("review_plan", "persist_plan")
builder.add_edge("persist_plan", "render_answer")
builder.add_edge("render_answer", END)

graph = builder.compile(
    checkpointer=postgres_checkpointer,
    store=postgres_store,
)
```

LangGraph persistence saves state by thread, supporting memory, fault recovery and human-in-the-loop continuation. Long-term farm data should be stored in a user- and farm-specific namespace rather than relying only on conversation history. ([Docs by LangChain][11])

---

# 7. Intake and routing pseudocode

## Do not use a generic intent classifier for every step

A farmer may say:

> “I have 3 bigha in Tanore and want to cultivate this winter.”

The model’s job is to extract known values. The workflow phase and missing fields should determine the route.

```python
class ExtractedFarmUpdate(BaseModel):
    location_text: str | None
    latitude: float | None
    longitude: float | None

    area_value: Decimal | None
    area_unit: Literal[
        "decimal", "bigha", "acre", "hectare"
    ] | None

    soil_type: str | None
    irrigation_available: bool | None
    water_source: str | None
    budget_bdt: Decimal | None
    season: str | None
    preferred_crops: list[str]
    previous_crop: str | None

    user_question_type: Literal[
        "create_plan",
        "update_profile",
        "select_crop",
        "modify_plan",
        "explain_recommendation",
        "what_if",
        "report_observation",
        "general_question",
    ]


async def extract_profile_updates(
    state: AgriSenseState,
) -> dict:
    structured_model = llm.with_structured_output(
        ExtractedFarmUpdate
    )

    extracted = await structured_model.ainvoke(
        [
            SYSTEM(
                """
                Extract only facts explicitly stated by the farmer.
                Never infer soil type, water access, farm size, budget,
                season or location.

                Convert nothing yet.
                Return null for absent or ambiguous information.
                """
            ),
            state.messages[-1],
        ]
    )

    return {
        "farm_profile": merge_explicit_updates(
            state.farm_profile,
            extracted,
        ),
        "last_request_type": extracted.user_question_type,
    }
```

Structured-output schemas avoid fragile parsing of natural-language model responses. ([Docs by LangChain][12])

## Deterministic validation

```python
REQUIRED_FIELDS = [
    "location",
    "area",
    "soil_or_land_context",
    "water_availability",
    "budget",
    "season",
]


def validate_profile(state: AgriSenseState) -> dict:
    profile = state.farm_profile

    errors = []
    missing = []

    if not any([
        profile.latitude and profile.longitude,
        profile.upazila_code,
        profile.location_text,
    ]):
        missing.append("location")

    if profile.area_hectare is None:
        if profile.original_area_value is None:
            missing.append("farm_size")
        elif profile.original_area_unit is None:
            missing.append("farm_size_unit")

    if (
        profile.soil_texture is None
        and profile.latitude is None
        and profile.union is None
    ):
        missing.append("soil_or_precise_location")

    if profile.irrigation_available is None:
        missing.append("water_availability")

    if profile.budget_bdt is None:
        missing.append("budget")

    if profile.season is None:
        missing.append("target_season")

    if profile.budget_bdt is not None and profile.budget_bdt <= 0:
        errors.append("Budget must be greater than zero.")

    if profile.original_area_value is not None:
        if profile.original_area_value <= 0:
            errors.append("Farm area must be greater than zero.")

    return {
        "missing_fields": prioritize_missing_fields(missing),
        "validation_errors": errors,
    }
```

## Ask only one or two targeted questions

```python
def ask_targeted_question(state):
    field = state.missing_fields[0]

    questions = {
        "location":
            "Where is the farm? You can provide the village/upazila "
            "or place a pin on the map.",

        "farm_size":
            "How large is the field?",

        "farm_size_unit":
            "Is that in decimal, bigha, acre or hectare?",

        "soil_or_precise_location":
            "Do you know the soil type, or can you provide the union "
            "or a map pin so I can retrieve the local land information?",

        "water_availability":
            "Do you have irrigation water during the season? "
            "For example, deep tube well, shallow pump or pond?",

        "budget":
            "Approximately how much can you spend on this field "
            "during the season?",

        "target_season":
            "Which season are you planning for: Rabi, Kharif-1, "
            "Kharif-2, or a particular month?",
    }

    return {
        "messages": [
            AIMessage(content=questions[field])
        ]
    }
```

This directly satisfies the brief’s targeted missing-information requirement rather than guessing. 

---

# 8. Location and land-context resolution

```python
async def resolve_location(state, runtime):
    profile = state.farm_profile

    if profile.latitude and profile.longitude:
        administrative_area = await reverse_geocode(
            profile.latitude,
            profile.longitude,
        )

    else:
        candidates = await geocode(profile.location_text)

        if len(candidates) == 0:
            return Command(
                update={
                    "validation_errors": [
                        "Location could not be resolved."
                    ]
                },
                goto="ask_targeted_question",
            )

        if len(candidates) > 1:
            selection = interrupt({
                "type": "choose_location",
                "options": candidates,
            })

            administrative_area = candidates[
                selection["option_index"]
            ]

        else:
            administrative_area = candidates[0]

    return {
        "farm_profile": update_profile_location(
            profile,
            administrative_area,
        )
    }


async def fetch_land_context(state):
    p = state.farm_profile

    context = await czis_adapter.resolve_land_context(
        upazila_code=p.upazila_code,
        latitude=p.latitude,
        longitude=p.longitude,
        union=p.union,
    )

    confidence = 0.95 if context.point_matched else 0.65

    warnings = []
    if not context.point_matched:
        warnings.append(
            "Only upazila-level land information was available. "
            "The exact field may have different soil or drainage."
        )

    evidence = make_evidence(
        source="CZIS",
        request_parameters={
            "upazila_code": p.upazila_code,
            "lat": p.latitude,
            "lon": p.longitude,
        },
        normalized_values=context.model_dump(),
        confidence=confidence,
        warnings=warnings,
    )

    return {
        "land_context": context,
        "evidence_ledger": [evidence],
        "warnings": warnings,
    }
```

---

# 9. Live-weather retrieval

Open-Meteo’s forecast API supports forecasts of up to 16 days and exposes precipitation, temperature, relative humidity, ET₀, soil temperature and soil-moisture variables. ET₀ is specifically useful when estimating crop irrigation demand. ([Open-Meteo][13])

```python
async def fetch_weather(state):
    p = state.farm_profile

    raw = await weather_client.forecast(
        latitude=p.latitude,
        longitude=p.longitude,
        timezone="Asia/Dhaka",
        forecast_days=16,
        daily=[
            "temperature_2m_min",
            "temperature_2m_max",
            "precipitation_sum",
            "precipitation_probability_max",
            "et0_fao_evapotranspiration",
            "wind_speed_10m_max",
        ],
        hourly=[
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "soil_temperature_6cm",
            "soil_moisture_3_to_9cm",
        ],
    )

    normalized = normalize_weather(raw)

    return {
        "weather_snapshot": normalized,
        "evidence_ledger": [
            make_evidence(
                source="Open-Meteo",
                request_parameters=raw.request_parameters,
                normalized_values=normalized.summary,
                confidence=0.8,
                warnings=[
                    "Forecast values are model estimates, "
                    "not measurements from the field."
                ],
            )
        ],
    }
```

Do not use seasonal forecasts as exact local weather. Longer-range seasonal products have much coarser resolution and should only indicate whether conditions may be wetter, drier, hotter or cooler than average. ([Open-Meteo][14])

---

# 10. Candidate generation and crop ranking

## Candidate generation

```python
async def generate_candidates(state):
    suitability_rows = await czis_adapter.get_crop_suitability(
        location=state.land_context,
        season=state.farm_profile.season,
    )

    eligible = []

    for row in suitability_rows:
        if row.suitability_class == "not_suitable":
            continue

        if row.crop in state.farm_profile.excluded_crops:
            continue

        if not bamis_repository.has_calendar(
            crop=row.crop,
            region=map_to_bamis_region(state.farm_profile),
        ):
            # May still be considered, but mark lower support.
            row.warnings.append("No normalized BAMIS calendar available.")

        eligible.append(row)

    # Keep a manageable number before detailed evaluation.
    return {
        "candidate_crop_ids": select_top_by_czis(
            eligible,
            limit=8,
        )
    }
```

## Parallel evaluation with `Send`

```python
def fan_out_crop_evaluations(state):
    return [
        Send(
            "evaluate_crop",
            {
                "crop_id": crop_id,
                "farm_profile": state.farm_profile,
                "land_context": state.land_context,
                "weather_snapshot": state.weather_snapshot,
            },
        )
        for crop_id in state.candidate_crop_ids
    ]
```

## Transparent weighted ranking

The weights below are product-design choices, not official BARC weights. Keep them in configuration and show them in the trace.

```python
WEIGHTS = {
    "land_suitability": 0.40,
    "season_and_weather_fit": 0.20,
    "water_feasibility": 0.15,
    "budget_feasibility": 0.10,
    "economic_outlook": 0.10,
    "rotation_and_preference": 0.05,
}


async def evaluate_crop(candidate_state):
    crop = load_crop(candidate_state.crop_id)
    profile = candidate_state.farm_profile
    land = candidate_state.land_context
    weather = candidate_state.weather_snapshot

    suitability = score_czis_suitability(
        crop=crop,
        land=land,
    )

    calendar = bamis_repository.get_calendar(
        crop=crop,
        region=map_to_bamis_region(profile),
        season=profile.season,
    )

    weather_fit = compare_forecast_to_crop_requirements(
        weather=weather,
        calendar=calendar,
        intended_sowing_window=profile.desired_sowing_window,
    )

    water_score = calculate_water_feasibility(
        crop_water_requirements=calendar.water_requirements,
        rainfall_forecast=weather.rainfall,
        irrigation_available=profile.irrigation_available,
        irrigation_capacity=profile.irrigation_capacity,
    )

    rough_cost = estimate_preliminary_cost(
        crop=crop,
        area_ha=profile.area_hectare,
        irrigation_requirement=calendar.water_requirements,
    )

    budget_score = score_budget_fit(
        estimated_cost=rough_cost,
        farmer_budget=profile.budget_bdt,
    )

    economic = estimate_economic_outlook(
        crop=crop,
        suitability=suitability,
        current_price_data=market_repository.get(crop),
    )

    rotation_score = score_rotation(
        previous_crop=profile.previous_crop,
        candidate_crop=crop,
        farmer_preferences=profile.preferred_crops,
    )

    total = weighted_sum({
        "land_suitability": suitability.score,
        "season_and_weather_fit": weather_fit.score,
        "water_feasibility": water_score,
        "budget_feasibility": budget_score,
        "economic_outlook": economic.score,
        "rotation_and_preference": rotation_score,
    }, WEIGHTS)

    return {
        "crop_evaluations": [
            CropEvaluation(
                crop_name=crop.name,
                total_score=total,
                risk_level=derive_risk_level(
                    suitability,
                    weather_fit,
                    water_score,
                    economic,
                ),
                limiting_factors=collect_limiting_factors(...),
                supporting_evidence_ids=collect_evidence_ids(...),
                ...
            )
        ]
    }
```

## Rank and return at least three

```python
def rank_candidates(state):
    valid = [
        result
        for result in state.crop_evaluations
        if result.budget_feasibility_score > MINIMUM_BUDGET_FIT
    ]

    ranked = sorted(
        valid,
        key=lambda x: (
            x.total_score,
            -risk_sort_value(x.risk_level),
        ),
        reverse=True,
    )

    return {"crop_evaluations": ranked[:3]}
```

Output example:

```text
1. Mustard - suitability 84/100
   Water need: low to moderate
   Risk: low
   Estimated investment: BDT ...
   Base expected profit: BDT ...
   Why: suitable Tanore land class, Rabi temperature fit,
        irrigation availability is sufficient.

2. Potato - suitability 79/100
   Water need: moderate
   Risk: medium
   Why: strong market potential, but higher budget and
        temperature/disease sensitivity.

3. Wheat - suitability 74/100
   Water need: moderate
   Risk: low to medium
```

---

# 11. Human crop selection

The agent should recommend but not silently choose the farmer’s crop.

```python
def select_crop(state):
    decision = interrupt({
        "type": "select_crop",
        "message": "Choose a crop or request a comparison.",
        "options": [
            {
                "crop": c.crop_name,
                "score": c.total_score,
                "risk": c.risk_level,
                "estimated_cost": str(c.expected_cost),
                "estimated_profit_range": [
                    str(c.expected_revenue_low - c.expected_cost),
                    str(c.expected_revenue_high - c.expected_cost),
                ],
                "limiting_factors": c.limiting_factors,
            }
            for c in state.crop_evaluations
        ],
    })

    selected = find_candidate(
        state.crop_evaluations,
        decision["crop"],
    )

    return {
        "selected_crop": selected,
        "phase": "plan_generation",
    }
```

LangGraph interruptions persist graph state and can be resumed later using the same thread ID and `Command(resume=...)`. Nodes containing interrupts may restart from the beginning, so any preceding side effect must be idempotent. ([Docs by LangChain][15])

---

# 12. Deterministic fertilizer engine

```python
async def calculate_fertilizer(state):
    profile = state.farm_profile
    crop = state.selected_crop

    if has_valid_recent_soil_test(profile):
        fertility_classes = {}

        for nutrient in SUPPORTED_NUTRIENTS:
            fertility_classes[nutrient] = (
                frg_repository.classify_soil_test(
                    nutrient=nutrient,
                    measured_value=getattr(profile, nutrient),
                    test_method=profile.soil_test_method,
                    land_environment=state.land_context.environment,
                )
            )

        recommendation_mode = "soil_test_based"
        confidence = 0.90

        nutrient_targets = (
            frg_repository.lookup_soil_test_recommendation(
                crop=crop.crop_name,
                land_environment=state.land_context.environment,
                fertility_classes=fertility_classes,
                yield_goal=select_realistic_yield_goal(crop),
            )
        )

    else:
        recommendation_mode = "aez_cropping_pattern_fallback"
        confidence = 0.65

        nutrient_targets = (
            frg_repository.lookup_aez_pattern_recommendation(
                crop=crop.crop_name,
                ae_zone=state.land_context.ae_zone,
                season=profile.season,
                irrigation_status=profile.irrigation_available,
            )
        )

    fertilizer_products = convert_nutrients_to_products(
        nutrient_targets=nutrient_targets,
        product_composition_table=approved_fertilizer_products,
    )

    scaled = scale_to_area(
        fertilizer_products,
        area_ha=profile.area_hectare,
    )

    stage_schedule = create_split_schedule(
        crop=crop.crop_name,
        recommendations=scaled,
        frg_split_rules=nutrient_targets.split_rules,
    )

    weather_adjusted = apply_weather_safety_windows(
        schedule=stage_schedule,
        forecast=state.weather_snapshot,
        rules=agronomic_weather_rules,
    )

    return {
        "fertilizer_plan": weather_adjusted.tasks,
        "warnings": weather_adjusted.warnings,
        "evidence_ledger": [
            make_evidence(
                source="BARC FRG 2024",
                request_parameters={
                    "crop": crop.crop_name,
                    "ae_zone": state.land_context.ae_zone,
                    "soil_test_available": has_valid_recent_soil_test(profile),
                    "fertility_classes": fertility_classes
                        if has_valid_recent_soil_test(profile)
                        else None,
                },
                normalized_values={
                    "recommendation_mode": recommendation_mode,
                    "nutrient_targets": nutrient_targets,
                    "product_quantities": scaled,
                },
                confidence=confidence,
                warnings=[] if confidence > 0.8 else [
                    "No field soil test was provided. "
                    "The recommendation uses generalized AEZ guidance."
                ],
            )
        ],
    }
```

## Important arithmetic separation

```python
def convert_nutrients_to_products(
    nutrient_targets,
    product_composition_table,
):
    """
    Example concept:
        required_product_mass =
            required_nutrient_mass /
            product_nutrient_fraction

    Actual product mappings and composition percentages must come
    from a reviewed configuration or official source.
    """

    result = {}

    for nutrient, required_kg_ha in nutrient_targets.items():
        product = choose_approved_product(nutrient)
        fraction = product_composition_table[
            product
        ].nutrient_fraction

        result[product] = quantize_decimal(
            required_kg_ha / fraction
        )

    return result
```

The LLM does not perform these calculations.

---

# 13. Season-calendar builder

```python
async def build_crop_calendar(state):
    crop = state.selected_crop.crop_name
    region = map_to_bamis_region(state.farm_profile)

    template = bamis_repository.get_calendar(
        crop=crop,
        region=region,
        season=state.farm_profile.season,
    )

    sowing_window = choose_sowing_window(
        official_window=template.sowing_window,
        farmer_preference=state.farm_profile.desired_sowing_window,
        forecast=state.weather_snapshot,
    )

    tasks = []

    for stage in template.stages:
        stage_start = sowing_window.start + timedelta(
            days=stage.start_day_after_sowing
        )
        stage_end = sowing_window.start + timedelta(
            days=stage.end_day_after_sowing
        )

        tasks.extend(
            instantiate_stage_tasks(
                crop=crop,
                stage=stage,
                start=stage_start,
                end=stage_end,
            )
        )

    return {
        "season_plan": tasks,
        "evidence_ledger": [
            make_evidence(
                source="BAMIS crop weather calendar",
                request_parameters={
                    "crop": crop,
                    "region": region,
                },
                normalized_values={
                    "stages": template.stages,
                    "sowing_window": sowing_window,
                },
                confidence=0.80,
            )
        ],
    }
```

---

# 14. Irrigation and weather-aware scheduling

```python
async def calculate_irrigation(state):
    crop_calendar = get_selected_calendar(state)
    weather = state.weather_snapshot
    soil = state.land_context
    area = state.farm_profile.area_hectare

    tasks = []

    for stage in crop_calendar.stages:
        crop_coefficient = crop_calendar.crop_coefficient_by_stage[
            stage.name
        ]

        stage_et0 = weather.sum_et0(stage.date_range)
        estimated_crop_water_mm = stage_et0 * crop_coefficient

        effective_rainfall_mm = estimate_effective_rainfall(
            rainfall=weather.rainfall(stage.date_range),
            soil_texture=soil.soil_texture,
            drainage=soil.drainage,
        )

        net_irrigation_mm = max(
            Decimal("0"),
            estimated_crop_water_mm - effective_rainfall_mm,
        )

        irrigation_volume_m3 = (
            net_irrigation_mm
            / Decimal("1000")
            * hectare_to_square_meter(area)
        )

        if irrigation_volume_m3 > 0:
            tasks.append(
                make_irrigation_task(
                    stage=stage,
                    volume_m3=irrigation_volume_m3,
                    reason={
                        "stage_et0_mm": stage_et0,
                        "crop_coefficient": crop_coefficient,
                        "effective_rainfall_mm": effective_rainfall_mm,
                    },
                )
            )

    return {"irrigation_plan": tasks}
```

For the hackathon, do not pretend this is precision irrigation unless crop coefficients and effective-rainfall logic are properly sourced. A simpler stage-based irrigation checkpoint is preferable to a fake high-precision answer.

---

# 15. Pest and disease risk

```python
def calculate_risks(state):
    calendar = get_selected_calendar(state)
    forecast = state.weather_snapshot
    risks = []

    current_and_future_stages = stages_within_forecast_window(
        calendar,
        forecast.date_range,
    )

    for rule in calendar.disease_weather_rules:
        if rule.stage not in current_and_future_stages:
            continue

        matched = evaluate_weather_rule(
            rule=rule,
            forecast=forecast,
        )

        if matched:
            risks.append(
                {
                    "hazard": rule.hazard,
                    "level": derive_risk_level(rule, forecast),
                    "window": matched.window,
                    "preventive_action": rule.preventive_action,
                    "evidence": rule.source_reference,
                }
            )

    return {"risk_alerts": risks}
```

The model may explain a risk, but the trigger itself should be a deterministic comparison against structured conditions.

---

# 16. Financial projection

The Department of Agricultural Marketing exposes recent prices and reports that can be filtered by district, upazila, market and date. ([Dam Market][16])

However, the visible values may be retail-market prices. Farmer revenue should ideally use farmgate or wholesale prices. Never silently treat retail price as the price the farmer will receive.

```python
async def fetch_market_and_costs(state):
    crop = state.selected_crop.crop_name
    location = state.farm_profile

    market_result = await market_adapter.find_prices(
        crop=crop,
        district=location.district,
        upazila=location.upazila,
        date=today(),
    )

    if market_result.has_farmgate_or_wholesale:
        price_basis = market_result.best_relevant_price
        confidence = 0.80

    elif market_result.has_retail:
        price_basis = derive_conservative_estimate_from_retail(
            retail_range=market_result.retail_range,
            configured_marketing_margin=CONFIGURED_MARGIN,
        )
        confidence = 0.50

    else:
        price_basis = seeded_price_catalog.get(crop)
        confidence = 0.35

    costs = cost_catalog.get_crop_costs(
        crop=crop,
        location=location,
    )

    return {
        "market_and_cost_data": {
            "price": price_basis,
            "costs": costs,
            "confidence": confidence,
        },
        "warnings": build_price_warnings(confidence),
    }
```

## Financial formulas

```python
def calculate_financials(state):
    area = state.farm_profile.area_hectare
    evaluation = state.selected_crop
    prices = state.market_and_cost_data.price
    cost_items = build_cost_items(state)

    total_variable_cost = sum(
        item.total
        for item in cost_items
        if item.type == "variable"
    )

    total_fixed_cost = sum(
        item.total
        for item in cost_items
        if item.type == "fixed"
    )

    total_cost = total_variable_cost + total_fixed_cost

    yields = {
        "low": evaluation.expected_yield_low * area,
        "base": evaluation.expected_yield_base * area,
        "high": evaluation.expected_yield_high * area,
    }

    revenues = {
        "low": yields["low"] * prices.low,
        "base": yields["base"] * prices.base,
        "high": yields["high"] * prices.high,
    }

    profits = {
        scenario: revenues[scenario] - total_cost
        for scenario in ["low", "base", "high"]
    }

    rois = {
        scenario: (
            profits[scenario] / total_cost * Decimal("100")
            if total_cost > 0
            else None
        )
        for scenario in ["low", "base", "high"]
    }

    break_even_yield = total_cost / prices.base
    break_even_price = total_cost / yields["base"]

    return {
        "financial_projection": FinancialProjection(
            cost_items=cost_items,
            total_variable_cost=total_variable_cost,
            total_fixed_cost=total_fixed_cost,
            total_cost=total_cost,
            yield_low=yields["low"],
            yield_base=yields["base"],
            yield_high=yields["high"],
            revenue_low=revenues["low"],
            revenue_base=revenues["base"],
            revenue_high=revenues["high"],
            net_profit_low=profits["low"],
            net_profit_base=profits["base"],
            net_profit_high=profits["high"],
            roi_low_pct=rois["low"],
            roi_base_pct=rois["base"],
            roi_high_pct=rois["high"],
            break_even_yield=break_even_yield,
            break_even_price=break_even_price,
            assumptions=state.financial_assumptions,
        )
    }
```

Use `Decimal`, not binary floating point, for financial values.

---

# 17. Final consistency validator

```python
def validate_plan(state):
    errors = []
    warnings = []

    plan = state.season_plan
    finance = state.financial_projection

    if len(state.crop_evaluations) < 3:
        errors.append("Fewer than three crops were ranked.")

    if state.selected_crop is None:
        errors.append("No crop has been selected.")

    if not every_task_has_date(plan):
        errors.append("Every task must have a concrete date window.")

    if tasks_overlap_impossibly(plan):
        errors.append("The generated task sequence contains conflicts.")

    if any_negative_quantity(plan):
        errors.append("A task has a negative quantity.")

    if finance.total_cost != sum(
        x.total for x in finance.cost_items
    ):
        errors.append("Financial cost items do not sum to total cost.")

    for scenario in ["low", "base", "high"]:
        expected_profit = (
            getattr(finance, f"revenue_{scenario}")
            - finance.total_cost
        )

        if getattr(finance, f"net_profit_{scenario}") != expected_profit:
            errors.append(
                f"{scenario} profit calculation is inconsistent."
            )

    if not all_numeric_claims_have_evidence(state):
        errors.append(
            "One or more important numeric claims lack evidence."
        )

    if state.confidence < 0.60:
        warnings.append(
            "The plan uses generalized data and should be confirmed "
            "with a local agricultural extension officer."
        )

    if errors:
        raise PlanValidationError(errors)

    return {
        "validation_errors": [],
        "warnings": warnings,
    }
```

---

# 18. Plan approval and persistence

```python
def review_plan(state):
    decision = interrupt({
        "type": "review_season_plan",
        "summary": {
            "crop": state.selected_crop.crop_name,
            "area_ha": str(state.farm_profile.area_hectare),
            "sowing_window": get_sowing_window(state),
            "total_cost_bdt": str(
                state.financial_projection.total_cost
            ),
            "expected_profit_range_bdt": [
                str(state.financial_projection.net_profit_low),
                str(state.financial_projection.net_profit_high),
            ],
            "important_assumptions": state.assumptions,
            "warnings": state.warnings,
        },
        "allowed_actions": [
            "approve",
            "change_crop",
            "change_budget",
            "change_sowing_date",
            "correct_farm_information",
        ],
    })

    if decision["action"] == "approve":
        return {
            "phase": "active_season",
            "plan_version": state.plan_version + 1,
        }

    if decision["action"] == "change_crop":
        return Command(
            update={"selected_crop": None},
            goto="present_candidates",
        )

    if decision["action"] in {
        "change_budget",
        "change_sowing_date",
        "correct_farm_information",
    }:
        return Command(
            update={
                "pending_profile_change": decision["changes"]
            },
            goto="extract_profile_updates",
        )
```

---

# 19. FastAPI chat pseudocode

```python
@app.post("/farms/{farm_id}/threads/{thread_id}/messages")
async def send_message(
    farm_id: UUID,
    thread_id: UUID,
    request: ChatRequest,
    auth: AuthenticatedUser = Depends(get_authenticated_user),
):
    assert_user_owns_farm(
        user_id=auth.user_id,
        farm_id=farm_id,
    )

    internal_thread_id = (
        f"org:{auth.organization_id}:"
        f"user:{auth.user_id}:"
        f"farm:{farm_id}:"
        f"thread:{thread_id}"
    )

    config = {
        "configurable": {
            "thread_id": internal_thread_id,
        },
        "recursion_limit": 80,
    }

    result = await graph.ainvoke(
        {
            "messages": [
                HumanMessage(content=request.message)
            ]
        },
        config=config,
        context=RuntimeContext(
            user_id=auth.user_id,
            organization_id=auth.organization_id,
            request_id=current_request_id(),
        ),
        version="v2",
    )

    return serialize_graph_result(result)


@app.post("/farms/{farm_id}/threads/{thread_id}/resume")
async def resume_workflow(
    farm_id: UUID,
    thread_id: UUID,
    request: ResumeRequest,
    auth: AuthenticatedUser = Depends(get_authenticated_user),
):
    assert_user_owns_farm(auth.user_id, farm_id)

    internal_thread_id = build_internal_thread_id(
        auth,
        farm_id,
        thread_id,
    )

    result = await graph.ainvoke(
        Command(resume=request.decision),
        config={
            "configurable": {
                "thread_id": internal_thread_id
            }
        },
        context=RuntimeContext(
            user_id=auth.user_id,
            organization_id=auth.organization_id,
            request_id=current_request_id(),
        ),
        version="v2",
    )

    return serialize_graph_result(result)
```

Never accept `user_id` or farm ownership from the model or request body. Obtain them from the authenticated runtime context.

---

# 20. Visible agent trace

The judges specifically need to inspect tool calls, parameters and returned values. 

Show an **evidence trace**, not hidden chain-of-thought:

```json
{
  "step": "fetch_weather",
  "status": "completed",
  "parameters": {
    "latitude": 24.58,
    "longitude": 88.58,
    "forecast_days": 16
  },
  "returned_values": {
    "next_7_day_rainfall_mm": 12.4,
    "min_temperature_c": 16.2,
    "max_temperature_c": 29.1
  },
  "source": "Open-Meteo",
  "fetched_at": "2026-07-24T10:35:00+06:00"
}
```

```json
{
  "step": "fertilizer_calculation",
  "status": "completed",
  "parameters": {
    "crop": "Mustard",
    "area_hectare": 0.401,
    "soil_test_available": false,
    "recommendation_mode": "AEZ fallback"
  },
  "returned_values": {
    "source_table": "...",
    "source_page": 173,
    "scaled_product_quantities": {
      "...": "..."
    }
  },
  "formula": "rate_per_hectare × farm_area_hectare",
  "warning": "Generalized recommendation; no field soil test provided"
}
```

Every number in the final output should point to one or more `evidence_id` values.

---

# 21. Continuous advisory loop

Tier 1 specifically rewards persistent memory, proactive weather-triggered changes, stage-specific scheduling and what-if simulation. 

```python
@scheduled_daily(hour=5, timezone="Asia/Dhaka")
async def monitor_active_plans():
    active_plans = db.get_active_plans(
        next_task_within_days=16
    )

    for plan in active_plans:
        await advisory_queue.enqueue(
            monitor_one_plan,
            plan_id=plan.id,
            idempotency_key=f"{plan.id}:{today()}",
        )


async def monitor_one_plan(plan_id):
    plan = db.get_plan_for_update(plan_id)
    farm = db.get_farm(plan.farm_id)

    new_weather = await weather_client.forecast(
        farm.latitude,
        farm.longitude,
        forecast_days=16,
    )

    previous_weather = plan.last_weather_snapshot

    changes = detect_material_weather_changes(
        previous=previous_weather,
        current=new_weather,
    )

    impacted_tasks = find_weather_sensitive_tasks(
        plan.tasks,
        weather_window=new_weather.date_range,
    )

    proposed_changes = []

    for task in impacted_tasks:
        evaluation = evaluate_task_against_weather(
            task=task,
            weather=new_weather,
            crop_rules=plan.crop_weather_rules,
        )

        if evaluation.should_reschedule:
            proposed_changes.append(
                propose_rescheduled_task(
                    task,
                    evaluation.safe_window,
                    reason=evaluation.reason,
                )
            )

    if proposed_changes:
        revision = create_plan_revision(
            original_plan=plan,
            proposed_changes=proposed_changes,
            new_weather=new_weather,
        )

        db.save_revision(revision)

        await notification_service.send(
            user_id=plan.user_id,
            message=render_advisory(revision),
        )

    db.update_last_weather_snapshot(
        plan_id,
        new_weather,
    )
```

Example user notification:

```text
Rainfall is now forecast during your planned nitrogen application
window.

Suggested change:
Move the application from 8 November to 11 November.

Why:
- Planned task: nitrogen top dressing
- Forecast rainfall on 8-9 November: ...
- Next lower-rain window: 11 November
- Crop stage remains within the approved application window

This is a proposed revision. Confirm before updating the plan.
```

---

# 22. Handling common data conflicts

Use an explicit precedence policy:

```python
SOURCE_PRECEDENCE = {
    "fertilizer_quantity": [
        "recent_valid_soil_test + FRG rule",
        "CZIS point recommendation",
        "CZIS union recommendation",
        "FRG AEZ/cropping-pattern recommendation",
    ],

    "crop_candidate_suitability": [
        "CZIS point/polygon suitability",
        "CZIS union suitability",
        "CZIS upazila suitability",
    ],

    "crop_stage_timing": [
        "BAMIS crop-region calendar",
        "official crop production manual",
    ],

    "near_term_weather": [
        "live forecast API",
    ],

    "farmer_revenue_price": [
        "farmgate price",
        "wholesale market price",
        "conservatively adjusted retail price",
        "clearly marked seeded estimate",
    ],
}
```

Conflict example:

```python
if czis_says_suitable and bamis_weather_window_is_bad:
    # Do not discard the crop permanently.
    recommendation = {
        "crop": crop,
        "land_fit": "good",
        "current_sowing_window_fit": "poor",
        "decision": "delay sowing or rank below alternatives",
    }
```

CZIS answers whether the land is suitable. BAMIS plus live weather answers whether **now** is a good time.

---

# 23. What must be real and what may be mocked

For the demo:

| Component                            | Recommended status                                      |
| ------------------------------------ | ------------------------------------------------------- |
| Weather API call                     | Real                                                    |
| Farmer conversation and memory       | Real                                                    |
| CZIS Tanore extraction               | Real or cached official snapshot, clearly labelled      |
| BAMIS calendar extraction            | Real preprocessed official data                         |
| FRG RAG retrieval                    | Real                                                    |
| Fertilizer rules for supported crops | Real and manually validated                             |
| Financial arithmetic                 | Real deterministic calculation                          |
| Input cost catalog                   | Seeded/mock is acceptable if disclosed                  |
| Market price                         | Real when accessible; otherwise clearly marked estimate |
| Notifications                        | Can be simulated                                        |
| Payment                              | Skip until Tier 0 is stable                             |

The judging gives the largest combined weight to agentic behavior, accuracy, practicality, scope execution and the knowledge base. Payment is valuable, but only after the agricultural core works reliably. 

---

# Final recommended workflow

```text
Farmer begins vague conversation
    ↓
Extract only explicit facts
    ↓
Load remembered farm profile
    ↓
Validate required slots
    ↓
Ask only for the next missing/ambiguous input
    ↓
Resolve GPS / upazila / union
    ↓
Retrieve CZIS land and suitability context
    ↓
Fetch 16-day live weather
    ↓
Generate crop candidates from CZIS
    ↓
Evaluate candidates in parallel using:
    - CZIS suitability
    - BAMIS calendar fit
    - live weather
    - irrigation feasibility
    - budget
    - market/cost assumptions
    ↓
Return top 3 with risk, water, cost and profit ranges
    ↓
Farmer selects crop
    ↓
Retrieve FRG evidence
    ↓
Calculate fertilizer deterministically
    ↓
Build dated BAMIS-based calendar
    ↓
Overlay weather-aware irrigation and fertilizer windows
    ↓
Calculate pest and disease risks
    ↓
Calculate deterministic cost, revenue, ROI and break-even
    ↓
Run consistency and evidence validation
    ↓
Farmer reviews and approves plan
    ↓
Persist farm profile and plan
    ↓
Daily weather monitor revises affected tasks
    ↓
Continue advising until harvest
```

The strongest version of this project is not the one that has the most tools. It is the one where a judge can change the area, budget, sowing date or irrigation availability and immediately see the candidate ranking, fertilizer quantities, schedule and financial numbers recompute consistently from traceable sources.

[1]: https://apps.barc.gov.bd/fertilizer_recommendation/FRG%20English%2030.10.2024.pdf "https://apps.barc.gov.bd/fertilizer_recommendation/FRG%20English%2030.10.2024.pdf"
[2]: https://www.bamis.gov.bd/en/calendar/ "https://www.bamis.gov.bd/en/calendar/"
[3]: https://czis.cropzoning.gov.bd/ "https://czis.cropzoning.gov.bd/"
[4]: https://portal.cropzoning.gov.bd/ "https://portal.cropzoning.gov.bd/"
[5]: https://apps.barc.gov.bd/cropzoning/homes/intro "https://apps.barc.gov.bd/cropzoning/homes/intro"
[6]: https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/b/V2Ministry/o/office-bbs/2024/12/31faf5cab9e14a42995e7fbf809e1ef2.pdf "https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/b/V2Ministry/o/office-bbs/2024/12/31faf5cab9e14a42995e7fbf809e1ef2.pdf"
[7]: https://docs.langchain.com/oss/python/langgraph/workflows-agents "https://docs.langchain.com/oss/python/langgraph/workflows-agents"
[8]: https://docs.langchain.com/oss/python/langgraph/graph-api "https://docs.langchain.com/oss/python/langgraph/graph-api"
[9]: https://www.bamis.gov.bd/en/crops/view/44/ "https://www.bamis.gov.bd/en/crops/view/44/"
[10]: https://apps.barc.gov.bd/maps/index.php "https://apps.barc.gov.bd/maps/index.php"
[11]: https://docs.langchain.com/oss/python/langgraph/persistence "https://docs.langchain.com/oss/python/langgraph/persistence"
[12]: https://docs.langchain.com/oss/python/langchain/structured-output "https://docs.langchain.com/oss/python/langchain/structured-output"
[13]: https://open-meteo.com/en/docs "https://open-meteo.com/en/docs"
[14]: https://open-meteo.com/en/docs/seasonal-forecast-api "https://open-meteo.com/en/docs/seasonal-forecast-api"
[15]: https://docs.langchain.com/oss/python/langgraph/interrupts "https://docs.langchain.com/oss/python/langgraph/interrupts"
[16]: https://market.dam.gov.bd/retail_price_commodity_report?L=E "https://market.dam.gov.bd/retail_price_commodity_report?L=E"
