"""Offline contract tests for the optional external research adapters."""
from __future__ import annotations

import httpx
import pytest

from app.adapters import research


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_search_web_normalizes_ddgs_results_and_caps_limit(monkeypatch):
    captured = {}

    def fake_text(query, max_results):
        captured.update(query=query, max_results=max_results)
        return [
            {
                "title": "  BARC crop guide  ",
                "href": "https://example.test/guide",
                "body": "  Practical notes  ",
            },
            {"title": "Missing URL", "body": "skip this result"},
        ]

    monkeypatch.setattr(research, "_ddgs_text", fake_text)

    result = await research.search_web(" mustard crop guidance ", max_results=99)

    assert captured == {"query": "mustard crop guidance", "max_results": 5}
    assert result["source"] == "DuckDuckGo search"
    assert result["content_trust"] == "untrusted_external_reference"
    assert result["results"] == [
        {
            "title": "BARC crop guide",
            "url": "https://example.test/guide",
            "snippet": "Practical notes",
        }
    ]


@pytest.mark.asyncio
async def test_search_web_surfaces_ddgs_failure_as_research_error(monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(research, "_ddgs_text", fail)

    with pytest.raises(research.ResearchError, match="web search is unavailable"):
        await research.search_web("rice")


@pytest.mark.asyncio
async def test_search_wikipedia_returns_plain_intro_and_source_url():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        params = dict(request.url.params)
        if params.get("list") == "search":
            return httpx.Response(
                200,
                json={
                    "query": {
                        "search": [
                            {
                                "pageid": 42,
                                "title": "Mustard (condiment)",
                                "snippet": "<span class='searchmatch'>Mustard</span> crop",
                            }
                        ]
                    }
                },
            )
        assert params["pageids"] == "42"
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "pageid": 42,
                            "title": "Mustard (condiment)",
                            "fullurl": "https://en.wikipedia.org/wiki/Mustard_(condiment)",
                            "extract": "Mustard is a condiment made from seeds.",
                        }
                    ]
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await research.search_wikipedia("mustard", client=client)

    assert len(requests) == 2
    assert result["source"] == "Wikipedia (en)"
    assert result["content_trust"] == "untrusted_external_reference"
    assert result["results"] == [
        {
            "title": "Mustard (condiment)",
            "url": "https://en.wikipedia.org/wiki/Mustard_(condiment)",
            "summary": "Mustard is a condiment made from seeds.",
            "search_snippet": "Mustard crop",
        }
    ]


@pytest.mark.asyncio
async def test_search_wikipedia_rejects_invalid_language_before_request():
    with pytest.raises(research.ResearchError, match="language"):
        await research.search_wikipedia("mustard", language="en/../../evil")


@pytest.mark.asyncio
async def test_search_wikipedia_surfaces_upstream_failure():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"info": "busy"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(research.ResearchError, match="Wikipedia is unavailable"):
            await research.search_wikipedia("mustard", client=client)
