"""Synthetic data generation for quick commerce scenarios."""

from __future__ import annotations

import csv
import random
from pathlib import Path


def _travel_minutes(point_a: tuple[float, float], point_b: tuple[float, float], speed_kmph: float) -> float:
    dx = point_a[0] - point_b[0]
    dy = point_a[1] - point_b[1]
    distance = (dx * dx + dy * dy) ** 0.5
    return round((distance / speed_kmph) * 60.0, 2)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_sample_data(data_dir: Path, seed: int = 7, order_count: int = 50, rider_count: int = 6) -> None:
    """Create a Blinkit-style sample dataset."""
    random.seed(seed)
    data_dir.mkdir(parents=True, exist_ok=True)
    average_speed_kmph = 18.0

    orders = []
    for order_id in range(1, order_count + 1):
        created_min = random.choice(range(0, 111, 5))
        promise_buffer = random.choice([10, 12, 15, 18, 20])
        basket_value = random.choice([180, 240, 320, 450, 600, 850])
        revenue = round(30 + basket_value * 0.18, 2)
        orders.append(
            {
                "id": order_id,
                "x": round(random.uniform(0.8, 7.0), 2),
                "y": round(random.uniform(0.5, 7.0), 2),
                "demand": 1,
                "created_min": created_min,
                "promise_min": created_min + promise_buffer,
                "basket_value": basket_value,
                "revenue": revenue,
                "is_premium": random.choice([0, 0, 1]),
            }
        )

    riders = []
    for rider_id in range(1, rider_count + 1):
        riders.append(
            {
                "id": rider_id,
                "capacity": 4,
                "start_x": 0.0,
                "start_y": 0.0,
                "shift_start_min": 0,
                "shift_end_min": 240,
            }
        )

    nodes = {0: (0.0, 0.0)}
    for order in orders:
        nodes[order["id"]] = (order["x"], order["y"])

    travel_rows = []
    for from_id, from_point in nodes.items():
        for to_id, to_point in nodes.items():
            if from_id == to_id:
                continue
            travel_rows.append(
                {
                    "from_id": from_id,
                    "to_id": to_id,
                    "minutes": _travel_minutes(from_point, to_point, average_speed_kmph),
                }
            )

    _write_csv(
        data_dir / "orders.csv",
        ["id", "x", "y", "demand", "created_min", "promise_min", "basket_value", "revenue", "is_premium"],
        orders,
    )
    _write_csv(
        data_dir / "riders.csv",
        ["id", "capacity", "start_x", "start_y", "shift_start_min", "shift_end_min"],
        riders,
    )
    _write_csv(
        data_dir / "travel_time.csv",
        ["from_id", "to_id", "minutes"],
        travel_rows,
    )
