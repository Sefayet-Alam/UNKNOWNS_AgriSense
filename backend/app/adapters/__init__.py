"""External data-source adapters (weather, CZIS, ...).

Adapters are plain async functions with injectable httpx clients so tests run
fully offline (httpx.MockTransport). They return normalized dicts carrying
evidence metadata (source, fetched_at, request params) — the agent's grounding
rule is that numbers shown to the farmer come from these adapters or the
deterministic engines, never from model recall.
"""
