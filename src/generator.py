"""Synthetic data generation for quick commerce scenarios."""

from __future__ import annotations

import csv
import random
from pathlib import Path


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_sample_data(data_dir: Path, seed: int = 7, order_count: int = 24, rider_count: int = 5) -> None:
    """Create a Blinkit-style sample dataset."""
    random.seed(seed)
    data_dir.mkdir(parents=True, exist_ok=True)

    orders = []
    for order_id in range(1, order_count + 1):
        created_min = random.choice(range(0, 91, 5))
        promise_buffer = random.choice([12, 15, 18, 20, 25])
        basket_value = random.choice([180, 240, 320, 450, 600, 850])
        revenue = round(30 + basket_value * 0.18, 2)
        orders.append(
            {
                "id": order_id,
                "x": round(random.uniform(0.8, 6.5), 2),
                "y": round(random.uniform(0.5, 6.5), 2),
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
                "shift_end_min": 180,
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
        [],
    )
