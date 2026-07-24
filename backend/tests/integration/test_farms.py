"""Integration tests for farm profile tools (user-scoped, DB-backed).

The tools are exercised directly (no LLM): they are what the model calls, so
their contract — auto-create + prefill, slot tracking, unit conversion,
plausibility warnings, strict user scoping — is the judged behavior.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.agent.tools import build_farm_tools, build_patterns_tool, build_soil_tool
from app.models import Farm, User

from tests.fakes import auth_headers_for

pytestmark = pytest.mark.integration


async def _db_user(db_session, phone: str) -> User:
    result = await db_session.execute(select(User).where(User.phone == phone))
    return result.scalar_one()


async def _tools_for(client, db_session, phone: str, **overrides):
    """Register a user via the real API, return {tool_name: tool}."""
    await auth_headers_for(client, phone=phone, **overrides)
    user = await _db_user(db_session, phone)
    tools = {t.name: t for t in build_farm_tools(user)}
    for extra in (build_soil_tool(user), build_patterns_tool(user)):
        tools[extra.name] = extra
    return tools


# --------------------------------------------------------------------------- #
# Auto-create + prefill
# --------------------------------------------------------------------------- #
async def test_first_profile_read_creates_farm_prefilled_from_registration(
    client, db_session
):
    tools = await _tools_for(client, db_session, "01712345001")
    payload = json.loads(await tools["get_farm_profile"].ainvoke({}))

    # Registration address (Tanore/Rajshahi from register_payload) prefills.
    assert payload["location"]["upazila"] == "Tanore"
    assert payload["location"]["upazila_code"] == "508194"
    assert payload["location"]["district"] == "Rajshahi"
    # Registration union pins the farm to its gazetteer centroid — weather
    # never needs live geocoding for the farmer's own field.
    assert payload["location"]["union"] == "Badhair"
    assert payload["location"]["union_geocode"] == "50819427"
    assert payload["location"]["latitude"] == pytest.approx(24.62968)
    assert payload["location"]["longitude"] == pytest.approx(88.44103)
    # Location satisfied by prefill; the rest is still missing.
    missing = payload["missing_required_fields"]
    # Soil auto-filled from the upazila survey (marked as a confirmable
    # default) — so it is NOT missing, but its source says "confirm".
    assert payload["soil_texture"] == "Clay Loam"
    assert payload["soil_source"] == "survey_default_confirm_with_farmer"
    assert "location" not in missing
    assert set(missing) == {"farm_size", "water_availability", "budget", "season"}
    assert payload["phase"] == "intake"


# --------------------------------------------------------------------------- #
# Slot filling + unit conversion
# --------------------------------------------------------------------------- #
async def test_update_fills_slots_and_converts_area(client, db_session):
    tools = await _tools_for(client, db_session, "01712345002")

    # Farmer: "৩ বিঘা, শ্যালো আছে" — bigha without local factor => ASSUMED.
    p1 = json.loads(
        await tools["update_farm_profile"].ainvoke(
            {
                "area_value": 3,
                "area_unit": "bigha",
                "irrigation_available": True,
                "water_source": "shallow tubewell",
            }
        )
    )
    assert p1["area"]["area_decimal"] == pytest.approx(99.0)
    assert p1["area"]["original_unit"] == "bigha"
    assert any("ASSUMED" in w for w in p1["warnings"])
    assert set(p1["missing_required_fields"]) == {"budget", "season"}

    # Farmer confirms the local bigha, gives budget + season + soil.
    p2 = json.loads(
        await tools["update_farm_profile"].ainvoke(
            {
                "area_value": 3,
                "area_unit": "bigha",
                "local_unit_factor_decimal": 33,
                "budget_bdt": 200000,
                "season": "winter",  # normalized -> rabi
                "soil_texture": "loam",
            }
        )
    )
    assert p2["area"]["area_decimal"] == pytest.approx(99.0)
    assert not any("ASSUMED" in w for w in p2["warnings"])
    assert p2["season"] == "rabi"
    assert p2["budget_bdt"] == 200000
    assert p2["missing_required_fields"] == []
    assert p2["phase"] == "ready_for_planning"


@pytest.mark.parametrize(
    "raw,expected",
    [("robi", "rabi"), ("রবি", "rabi"), ("winter", "rabi"), ("Kharif-2", "kharif-2")],
)
async def test_season_aliases_normalized(client, db_session, raw, expected):
    tools = await _tools_for(
        client, db_session, f"0171234{abs(hash(raw)) % 9000 + 1000}"
    )
    p = json.loads(await tools["update_farm_profile"].ainvoke({"season": raw}))
    assert p["season"] == expected


async def test_confirming_factor_alone_reconverts_stored_area(client, db_session):
    # Live-observed model behavior: after "৩ বিঘা" (assumed), the farmer says
    # "৩৩ শতক ধরে নেন" and the model passes ONLY local_unit_factor_decimal.
    tools = await _tools_for(client, db_session, "01712345010")
    await tools["update_farm_profile"].ainvoke(
        {"area_value": 2, "area_unit": "kani"}  # assumed 40 => 80
    )
    p = json.loads(
        await tools["update_farm_profile"].ainvoke(
            {"local_unit_factor_decimal": 48}  # farmer: locally 1 kani = 48
        )
    )
    assert p["area"]["area_decimal"] == pytest.approx(96.0)  # 2 x 48
    assert "farmer-confirmed" in p["area"]["conversion_note"]
    assert not any("ASSUMED" in w for w in p["warnings"])


async def test_area_without_unit_returns_error_asking_unit(client, db_session):
    tools = await _tools_for(client, db_session, "01712345003")
    resp = json.loads(await tools["update_farm_profile"].ainvoke({"area_value": 70}))
    assert "error" in resp
    assert "area_unit" in resp["error"]


async def test_implausible_area_budget_flagged_not_blocked(client, db_session):
    # EXAMPLE_FLOW #5: 300 bigha + 60k budget => warnings, values stored,
    # decision (confirm/correct) left to the conversation.
    tools = await _tools_for(client, db_session, "01712345004")
    p = json.loads(
        await tools["update_farm_profile"].ainvoke(
            {"area_value": 300, "area_unit": "bigha", "budget_bdt": 60000}
        )
    )
    assert p["area"]["area_decimal"] == pytest.approx(9900.0)
    assert any("unusually large" in w for w in p["warnings"])


async def test_location_change_reresolves_geocodes_and_coords(client, db_session):
    # EXAMPLE_FLOW #2: registered in Rajshahi, jomi in Naogaon (Manda).
    # Stale Rajshahi geocodes are cleared, then the bundled gazetteer
    # re-resolves "Manda" -> real upazila code + centroid coordinates.
    from app import geo

    tools = await _tools_for(client, db_session, "01712345005")
    p = json.loads(
        await tools["update_farm_profile"].ainvoke(
            {"upazila_name": "Manda", "district_name": "Naogaon"}
        )
    )
    manda = geo.find_upazila_by_name("Manda")
    assert manda is not None
    assert p["location"]["upazila"] == "Manda"
    assert p["location"]["upazila_code"] == manda["code"]
    assert p["location"]["district"] == "Naogaon"
    # Old union cannot survive an upazila change.
    assert p["location"]["union"] == ""
    # Coordinates re-pinned to the NEW place, not stale Rajshahi ones.
    assert p["location"]["latitude"] == pytest.approx(manda["lat"])
    assert p["location"]["longitude"] == pytest.approx(manda["lon"])
    assert any("location changed" in w for w in p["warnings"])


# --------------------------------------------------------------------------- #
# Soil (mandatory slot): survey auto-fill, SOIL_UNKNOWN ask-path, override
# --------------------------------------------------------------------------- #
async def test_soil_survey_prefill_and_tool_breakdown(client, db_session):
    # Prefill is MECHANICAL: farm creation already attached the survey
    # default (not model-driven), and the tool serves the full breakdown.
    tools = await _tools_for(client, db_session, "01712345020")
    profile = json.loads(await tools["get_farm_profile"].ainvoke({}))
    assert profile["soil_texture"] == "Clay Loam"
    assert profile["land_type"] == "High Land"
    assert profile["soil_source"] == "survey_default_confirm_with_farmer"
    assert "soil_type" not in profile["missing_required_fields"]

    payload = json.loads(await tools["get_soil_context"].ainvoke({}))
    assert payload["survey"]["texture"]["dominant"] == "Clay Loam"
    assert payload["survey"]["reaction"]["dominant"]  # pH class present
    assert "UPAZILA-LEVEL" in payload["note"]
    # Already filled at creation — the tool saved nothing new.
    assert payload["auto_saved_defaults"] == []


async def test_soil_unknown_location_clears_default_and_returns_sentinel(
    client, db_session
):
    # Farm moved to a place the gazetteer/survey doesn't know: the stale
    # survey default (old upazila's soil) must be CLEARED — soil_type goes
    # back to missing — and the tool says SOIL_UNKNOWN (=> agent must ask
    # the farmer). Never silently keep another upazila's soil.
    tools = await _tools_for(client, db_session, "01712345021")
    moved = json.loads(
        await tools["update_farm_profile"].ainvoke(
            {"upazila_name": "Nowhereville", "district_name": "Nowhere"}
        )
    )
    assert moved["soil_texture"] == ""
    assert "soil_type" in moved["missing_required_fields"]
    assert any("soil" in w.lower() for w in moved["warnings"])

    result = await tools["get_soil_context"].ainvoke({})
    assert result.startswith("SOIL_UNKNOWN")
    assert "ask" in result.lower()


async def test_location_change_refreshes_survey_soil_default(client, db_session):
    # Survey-default soil must FOLLOW the farm when it moves to a surveyed
    # upazila — Tanore's default is replaced by Manda's, still marked.
    from app import geo, soil

    tools = await _tools_for(client, db_session, "01712345024")
    p = json.loads(
        await tools["update_farm_profile"].ainvoke(
            {"upazila_name": "Manda", "district_name": "Naogaon"}
        )
    )
    manda = geo.find_upazila_by_name("Manda")
    expected = soil.dominant(manda["code"], "texture")
    assert expected  # Manda is surveyed
    assert p["soil_texture"] == expected
    assert p["soil_source"] == "survey_default_confirm_with_farmer"


async def test_farmer_statement_overrides_survey_default(client, db_session):
    tools = await _tools_for(client, db_session, "01712345022")
    # Farmer says sandy — replaces the survey default and drops the marker.
    p = json.loads(
        await tools["update_farm_profile"].ainvoke({"soil_texture": "sandy"})
    )
    assert p["soil_texture"] == "sandy"
    assert p["soil_source"] == "farmer_stated"

    # The tool must not overwrite a farmer statement.
    payload = json.loads(await tools["get_soil_context"].ainvoke({}))
    assert not any("soil_texture=" in s for s in payload["auto_saved_defaults"])

    # And moving the farm must NOT resurrect a survey default over it.
    moved = json.loads(
        await tools["update_farm_profile"].ainvoke(
            {"upazila_name": "Manda", "district_name": "Naogaon"}
        )
    )
    assert moved["soil_texture"] == "sandy"
    assert moved["soil_source"] == "farmer_stated"


async def test_create_farm_resolves_geo_and_requires_full_intake(
    client, db_session
):
    # A new farm gets gazetteer codes + coords from its stated names, and
    # starts with the full mandatory-field checklist (soil included).
    from app import geo

    tools = await _tools_for(client, db_session, "01712345023")
    created = json.loads(
        await tools["create_farm"].ainvoke(
            {"name": "Manda Char", "upazila_name": "Manda", "district_name": "Naogaon"}
        )
    )
    manda = geo.find_upazila_by_name("Manda")
    assert created["location"]["upazila_code"] == manda["code"]
    assert created["location"]["latitude"] == pytest.approx(manda["lat"])
    missing = set(created["missing_required_fields"])
    assert {"farm_size", "water_availability", "budget", "season"} <= missing
    # Soil pre-filled from MANDA's survey (not the registration upazila's).
    from app import soil

    assert created["soil_texture"] == soil.dominant(manda["code"], "texture")
    assert created["soil_source"] == "survey_default_confirm_with_farmer"
    # And the soil tool now serves the NEW farm's upazila, not the old one's.
    soil_payload = json.loads(await tools["get_soil_context"].ainvoke({}))
    assert soil_payload["upazila_code"] == manda["code"]


# --------------------------------------------------------------------------- #
# Cropping-pattern economics tool (recorded profitability grounding)
# --------------------------------------------------------------------------- #
async def test_cropping_patterns_tool_serves_farm_upazila_sorted(
    client, db_session
):
    tools = await _tools_for(client, db_session, "01712345025")
    payload = json.loads(await tools["get_cropping_patterns"].ainvoke({}))
    assert payload["upazila_code"] == "508194"  # Tanore (registration prefill)
    assert payload["count"] >= 1
    margins = [
        float(p["gm_tk_per_decimal"])
        for p in payload["patterns"]
        if p.get("gm_tk_per_decimal") is not None
    ]
    assert margins == sorted(margins, reverse=True)
    assert "gm_tk_per_decimal" in payload["units"]
    assert "CZIS" in payload["source"]


async def test_cropping_patterns_unknown_location_returns_sentinel(
    client, db_session
):
    tools = await _tools_for(client, db_session, "01712345026")
    await tools["update_farm_profile"].ainvoke(
        {"upazila_name": "Nowhereville", "district_name": "Nowhere"}
    )
    result = await tools["get_cropping_patterns"].ainvoke({})
    assert result.startswith("PATTERNS_UNKNOWN")
    assert "invent" in result.lower()


async def test_union_change_within_upazila_resolves_geocode(client, db_session):
    tools = await _tools_for(client, db_session, "01712345015")
    p = json.loads(
        await tools["update_farm_profile"].ainvoke({"union_name": "Kalma"})
    )
    assert p["location"]["union"] == "Kalma"
    assert p["location"]["union_geocode"] == "50819454"
    assert p["location"]["latitude"] is not None


# --------------------------------------------------------------------------- #
# Multiple farms + strict user scoping (EXAMPLE_FLOW #8, #9)
# --------------------------------------------------------------------------- #
async def test_multiple_farms_and_selection(client, db_session):
    tools = await _tools_for(client, db_session, "01712345006")
    first = json.loads(await tools["get_farm_profile"].ainvoke({}))

    created = json.loads(
        await tools["create_farm"].ainvoke(
            {"name": "Godagari Riverside", "upazila_name": "Godagari"}
        )
    )
    assert created["is_active"] is True
    assert created["location"]["upazila"] == "Godagari"

    farms = json.loads(await tools["list_farms"].ainvoke({}))
    assert len(farms) == 2
    active = [f for f in farms if f["is_active"]]
    assert len(active) == 1 and active[0]["farm_id"] == created["farm_id"]

    back = json.loads(await tools["select_farm"].ainvoke({"farm_id": first["farm_id"]}))
    assert back["farm_id"] == first["farm_id"]
    assert back["is_active"] is True


async def test_farms_are_invisible_across_users(client, db_session):
    tools_a = await _tools_for(client, db_session, "01712345007")
    profile_a = json.loads(await tools_a["get_farm_profile"].ainvoke({}))
    await tools_a["update_farm_profile"].ainvoke(
        {"area_value": 99, "area_unit": "shotok", "budget_bdt": 100000}
    )

    tools_b = await _tools_for(
        client, db_session, "01812345008", username="Other Farmer"
    )
    # B's list must not contain A's farm.
    farms_b = json.loads(await tools_b["list_farms"].ainvoke({}))
    assert all(f["farm_id"] != profile_a["farm_id"] for f in farms_b)

    # B cannot select A's farm by id — ownership enforced in the query.
    resp = json.loads(
        await tools_b["select_farm"].ainvoke({"farm_id": profile_a["farm_id"]})
    )
    assert "error" in resp

    # And B's own profile is untouched by A's data.
    profile_b = json.loads(await tools_b["get_farm_profile"].ainvoke({}))
    assert profile_b["budget_bdt"] is None


async def test_update_persists_to_db_row(client, db_session):
    tools = await _tools_for(client, db_session, "01712345009")
    p = json.loads(
        await tools["update_farm_profile"].ainvoke(
            {
                "area_value": 70,
                "area_unit": "shotok",
                "budget_bdt": 80000,
                "season": "rabi",
                "irrigation_available": True,
                "soil_texture": "clay loam",
                "previous_crop": "aman rice",
                "add_excluded_crops": ["Potato"],
            }
        )
    )
    row = (
        await db_session.execute(select(Farm).where(Farm.id == p["farm_id"]))
    ).scalar_one()
    assert row.area_decimal == pytest.approx(70.0)
    assert row.budget_bdt == 80000
    assert row.season == "rabi"
    assert row.previous_crop == "aman rice"
    assert row.excluded_crops == ["potato"]
    assert row.soil_texture == "clay loam"
    assert row.phase == "ready_for_planning"
