# Deterministic Intake and Research Gate Design

## Goal

Prevent an incomplete farm profile from triggering planner, recommender, or
finance research flows, while keeping web and Wikipedia search available only
for an eligible, grounded request.

## Scope

- Set the per-request tool-round budget to six.
- Keep the existing tool-level research gate as defence in depth.
- Add a deterministic graph admission policy which overrides model routing for
  an incomplete profile and a personalised planning request.
- Make compulsory research dependent on a successful deterministic tool result
  instead of forcing it after an incomplete or invalid result.
- Replace five-crop routing assumptions with the current finance catalog and
  make the recommendation limit capable of returning up to fifty candidates.
- Correct stale prompts and tool documentation. Dated calendars and input
  schedules remain explicitly limited to their sourced five-crop Rabi path.

## Routing and Tool Policy

The graph receives the active farm snapshot before classification. When its
`missing_required_fields` is non-empty, a crop recommendation, farm-planning,
dated-plan, or finance request must route to `intake` regardless of the lite
classifier's answer. Standalone weather, disease, and general questions retain
their advisor route.

The recommender can force `rank_crop_candidates` first. It may force external
research only if that result is `status=ok`. Planner and finance flows must not
force external research until their profile and selected-crop validation has
passed. The tool-level `PROFILE_INCOMPLETE` response remains the fail-closed
fallback for direct calls or future graph regressions.

## Catalog and Prompt Contract

Crop selection recognition derives from the current finance catalog rather
than a hard-coded set of five names. Recommendation requests may ask for up to
50 ranked candidates, but default responses remain a concise shortlist. The
agent must clearly distinguish:

- catalog/finance/shortlist capability;
- the five sourced Rabi crops with dated calendars and schedules; and
- unavailable capability, which must return a structured status rather than
  invented advice.

## Verification

Tests will prove that an intentionally misclassified vague opening reaches
intake with no web/Wikipedia tool trace, research tools make no network call
before a complete profile, the profile gate test creates an authenticated user,
and catalog routing no longer relies on the original five names. Focused
streaming, graph, recommendation, and tool tests run against a unique test
database.
