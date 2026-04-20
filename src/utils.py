"""Shared utilities for the quick commerce optimizer."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


def default_config() -> dict:
    """Central model and simulation settings."""
    return {
        "simulation_minutes": 120,
        "horizon_minutes": 30,
        "step_minutes": 1,
        "average_speed_kmph": 18.0,
        "service_minutes": 4.0,
        "travel_cost_per_min": 1.2,
        "schedule_penalty": 20.0,
        "rejection_penalty": 45.0,
        "lateness_penalty_per_min": 7.5,
        "premium_bonus": 18.0,
        "basket_value_weight": 0.025,
        "urgency_reward": 1.4,
        "cluster_radius": 1.8,
        "cluster_bonus": 6.0,
        "load_threshold": 0.9,
        "priority_bonus": 9.0,
        "max_schedule_push_min": 30,
        "gurobi_license_required": False,
    }


def _load_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_orders(path: Path) -> list[dict]:
    """Load order data and initialize simulation state."""
    orders = []
    for row in _load_csv(path):
        orders.append(
            {
                "id": int(row["id"]),
                "x": float(row["x"]),
                "y": float(row["y"]),
                "demand": int(row["demand"]),
                "created_min": int(row["created_min"]),
                "promise_min": int(row["promise_min"]),
                "basket_value": float(row["basket_value"]),
                "revenue": float(row["revenue"]),
                "is_premium": int(row["is_premium"]) == 1,
                "status": "pending",
                "scheduled_for_min": int(row["created_min"]),
                "delivery_min": None,
                "assigned_rider_id": None,
                "decision_history": [],
            }
        )
    return orders


def load_riders(path: Path) -> list[dict]:
    riders = []
    for row in _load_csv(path):
        riders.append(
            {
                "id": int(row["id"]),
                "capacity": int(row["capacity"]),
                "start_x": float(row["start_x"]),
                "start_y": float(row["start_y"]),
                "shift_start_min": int(row["shift_start_min"]),
                "shift_end_min": int(row["shift_end_min"]),
            }
        )
    return riders


def ensure_results_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def save_timeline_csv(path: Path, timeline: list[dict]) -> None:
    if not timeline:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(timeline[0].keys()))
        writer.writeheader()
        writer.writerows(timeline)


def order_distance(order_a: dict, order_b: dict) -> float:
    return math.dist((order_a["x"], order_a["y"]), (order_b["x"], order_b["y"]))


def depot_distance(order: dict, depot: tuple[float, float] = (0.0, 0.0)) -> float:
    return math.dist((order["x"], order["y"]), depot)


def travel_minutes_between(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
    speed_kmph: float,
) -> float:
    return (math.dist(point_a, point_b) / speed_kmph) * 60.0


def cluster_score(order: dict, orders: list[dict], radius: float) -> int:
    return sum(
        1
        for other in orders
        if other["id"] != order["id"] and order_distance(order, other) <= radius
    )


def finalize_open_orders(orders: list[dict], simulation_end: int) -> None:
    """Convert unresolved orders into a final scheduled/rejected state for reporting."""
    for order in orders:
        if order["status"] == "pending":
            if order["scheduled_for_min"] <= simulation_end + 30:
                order["status"] = "scheduled"
            else:
                order["status"] = "rejected"


def summarize_results(orders: list[dict], riders: list[dict], timeline: list[dict], config: dict) -> dict:
    total_orders = len(orders)
    delivered = [order for order in orders if order["status"] == "delivered"]
    rejected = [order for order in orders if order["status"] == "rejected"]
    scheduled = [order for order in orders if order["status"] == "scheduled"]

    delivered_count = len(delivered)
    revenue = round(sum(order["revenue"] for order in delivered), 2)
    avg_delivery_time = round(
        sum(order["delivery_min"] - order["created_min"] for order in delivered) / delivered_count,
        2,
    ) if delivered_count else None
    on_time_count = sum(1 for order in delivered if order["delivery_min"] <= order["promise_min"])
    travel_minutes = sum(entry["travel_minutes"] for entry in timeline)
    total_rider_minutes = len(riders) * max(config["simulation_minutes"], 1)
    utilization = round(travel_minutes / total_rider_minutes, 3) if total_rider_minutes else 0.0

    return {
        "total_orders": total_orders,
        "delivered_orders": delivered_count,
        "scheduled_orders": len(scheduled),
        "rejected_orders": len(rejected),
        "accepted_pct": round(delivered_count / total_orders, 3) if total_orders else 0.0,
        "on_time_pct": round(on_time_count / delivered_count, 3) if delivered_count else 0.0,
        "avg_delivery_time_min": avg_delivery_time,
        "revenue": revenue,
        "travel_minutes": round(travel_minutes, 2),
        "rider_utilization": utilization,
    }
