"""Deterministic engines (unit conversion, crop ranking, fertilizer, finance).

Core rule (docs/INSIGHTS.md, docs/PLAN.md): the LLM never computes the numbers
shown to a farmer. Every quantity comes from these pure, unit-tested functions
or from a real external adapter — the LLM only decides when to call them and
how to explain the results.
"""
