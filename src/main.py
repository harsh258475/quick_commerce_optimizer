"""Run a two-stage quick-commerce optimization simulation."""

from __future__ import annotations

import argparse
from pathlib import Path

from cuts import build_route_cut
from dashboard import print_dashboard
from generator import generate_sample_data
from master import solve_master_stage
from subproblem import repair_infeasible_acceptance
from utils import (
    default_config,
    ensure_results_dir,
    finalize_open_orders,
    load_orders,
    load_riders,
    save_json,
    save_timeline_csv,
    summarize_results,
)


def run_simulation(base_dir: Path, use_sample_data: bool = False) -> dict:
    """Run the rolling-horizon simulation and persist results."""
    data_dir = base_dir / "data"
    results_dir = ensure_results_dir(base_dir / "results")

    if use_sample_data:
        generate_sample_data(data_dir)

    orders = load_orders(data_dir / "orders.csv")
    riders = load_riders(data_dir / "riders.csv")
    config = default_config()

    horizon_end = max(
        config["simulation_minutes"],
        max((order["created_min"] for order in orders), default=0) + config["horizon_minutes"],
    )
    timeline = []
    cuts = []

    for current_minute in range(0, horizon_end + 1, config["step_minutes"]):
        visible_orders = [
            order
            for order in orders
            if order["status"] == "pending"
            and order["created_min"] <= current_minute
            and order["scheduled_for_min"] <= current_minute
        ]
        if not visible_orders:
            continue

        master_solution = solve_master_stage(visible_orders, riders, current_minute, config)
        accepted_ids = set(master_solution["accepted_ids"])
        accepted_orders = [order for order in visible_orders if order["id"] in accepted_ids]

        routing_solution, dropped_ids = repair_infeasible_acceptance(accepted_orders, riders, current_minute, config)
        if dropped_ids:
            cuts.append(build_route_cut(dropped_ids, current_minute))

        routed_ids = {
            stop["order_id"]
            for route in routing_solution["routes"]
            for stop in route["stops"]
        }
        dropped_set = set(dropped_ids)
        scheduled_ids = set(master_solution["scheduled_ids"]) | dropped_set | set(routing_solution["unrouted_ids"])
        rejected_ids = set(master_solution["rejected_ids"])

        for order in orders:
            order_id = order["id"]
            if order_id in routed_ids:
                stop = routing_solution["stop_lookup"][order_id]
                order["status"] = "delivered"
                order["delivery_min"] = round(stop["arrival_min"], 2)
                order["assigned_rider_id"] = stop["rider_id"]
                order["decision_history"].append({"minute": current_minute, "decision": "deliver"})
            elif order_id in scheduled_ids and order["status"] == "pending":
                order["scheduled_for_min"] = current_minute + config["step_minutes"]
                order["decision_history"].append({"minute": current_minute, "decision": "schedule"})
            elif order_id in rejected_ids and order["status"] == "pending":
                order["status"] = "rejected"
                order["decision_history"].append({"minute": current_minute, "decision": "reject"})

        timeline.append(
            {
                "minute": current_minute,
                "visible_orders": len(visible_orders),
                "accepted": len(accepted_orders) - len(dropped_ids),
                "scheduled": len(scheduled_ids),
                "rejected": len(rejected_ids),
                "routed": len(routed_ids),
                "travel_minutes": round(
                    sum(route["travel_minutes"] for route in routing_solution["routes"]),
                    2,
                ),
                "travel_cost": routing_solution["travel_cost"],
                "revenue": round(
                    sum(order["revenue"] for order in accepted_orders if order["id"] in routed_ids),
                    2,
                ),
                "master_solver": master_solution["solver"],
                "routing_solver": routing_solution["solver"],
            }
        )

    finalize_open_orders(orders, horizon_end)
    summary = summarize_results(orders, riders, timeline, config)
    result_bundle = {"summary": summary, "timeline": timeline, "orders": orders, "cuts": cuts}

    save_json(results_dir / "summary.json", result_bundle)
    save_timeline_csv(results_dir / "timeline.csv", timeline)
    return result_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quick commerce optimizer")
    parser.add_argument(
        "--sample-data",
        action="store_true",
        help="Regenerate sample input data before running the simulation.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    project_root = Path(__file__).resolve().parent.parent
    results = run_simulation(project_root, use_sample_data=args.sample_data)
    print_dashboard(results)
