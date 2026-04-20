"""Helpers for future Benders-style cuts and diagnostics."""

from __future__ import annotations


def build_route_cut(unrouted_ids: list[int], minute: int) -> dict:
    """Capture a simple feasibility issue from the routing stage."""
    return {"minute": minute, "type": "route_feasibility", "order_ids": unrouted_ids}


def summarize_cuts(cuts: list[dict]) -> str:
    """Return a small human-readable summary."""
    if not cuts:
        return "No route-feasibility cuts were generated."
    return f"{len(cuts)} route-feasibility cuts captured during rolling re-optimization."
