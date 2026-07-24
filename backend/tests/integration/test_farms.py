"""Integration tests for farm profile tools (user-scoped, DB-backed).

The tools are exercised directly (no LLM): they are what the model calls, so
their contract — auto-create + prefill, slot tracking, unit conversion,
plausibility warnings, strict user scoping — is the judged behavior.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.agent.tools import build_farm_tools
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
    return {t.name: t for t in build_farm_tools(user)}


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

    # Farmer confirms the local bigha and gives budget + season.
    p2 = json.loads(
        await tools["update_farm_profile"].ainvoke(
            {
                "area_value": 3,
                "area_unit": "bigha",
                "local_unit_factor_decimal": 33,
                "budget_bdt": 200000,
                "season": "winter",  # normalized -> rabi
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
    assert row.phase == "ready_for_planning"
