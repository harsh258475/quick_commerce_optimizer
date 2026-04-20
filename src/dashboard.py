"""Lightweight KPI reporting for the optimizer."""

from __future__ import annotations

import json
from pathlib import Path


def print_dashboard(results: dict) -> None:
    """Print the main KPIs to stdout."""
    summary = results["summary"]
    print("Quick Commerce KPI Dashboard")
    print(f"Total orders       : {summary['total_orders']}")
    print(f"Delivered orders   : {summary['delivered_orders']}")
    print(f"Scheduled orders   : {summary['scheduled_orders']}")
    print(f"Rejected orders    : {summary['rejected_orders']}")
    print(f"Accepted %         : {summary['accepted_pct']:.1%}")
    print(f"On-time %          : {summary['on_time_pct']:.1%}")
    print(f"Avg delivery (min) : {summary['avg_delivery_time_min']}")
    print(f"Revenue            : {summary['revenue']}")
    print(f"Travel minutes     : {summary['travel_minutes']}")
    print(f"Rider utilization  : {summary['rider_utilization']:.1%}")


def load_results(results_path: Path) -> dict:
    with results_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    results = load_results(project_root / "results" / "summary.json")
    print_dashboard(results)
