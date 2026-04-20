"""Stage 1: exact accept, schedule, or reject decisions."""

from __future__ import annotations

from typing import Iterable

from utils import cluster_score, depot_distance

try:
    import gurobipy as gp
    from gurobipy import GRB

    GUROBI_AVAILABLE = True
except ImportError:  # pragma: no cover
    gp = None
    GRB = None
    GUROBI_AVAILABLE = False


GUROBI_RUNTIME_AVAILABLE = True


def _accept_value(order: dict, visible_orders: list[dict], current_minute: int, config: dict) -> float:
    slack = max(order["promise_min"] - current_minute, 0)
    urgency_component = max(config["horizon_minutes"] - slack, 0) * config["urgency_reward"]
    premium_component = config["premium_bonus"] if order["is_premium"] else 0.0
    basket_component = order["basket_value"] * config["basket_value_weight"]
    cluster_component = cluster_score(order, visible_orders, config["cluster_radius"]) * config["cluster_bonus"]
    travel_component = depot_distance(order) * (60.0 / config["average_speed_kmph"]) * config["travel_cost_per_min"]
    return order["revenue"] + urgency_component + premium_component + basket_component + cluster_component - travel_component


def _priority_flag(order: dict, config: dict) -> bool:
    return order["is_premium"] or order["basket_value"] >= 450.0


def _fallback_master(orders: Iterable[dict], riders: list[dict], current_minute: int, config: dict) -> dict:
    visible_orders = list(orders)
    total_capacity = sum(rider["capacity"] for rider in riders)
    ranked_orders = sorted(
        visible_orders,
        key=lambda order: (
            -_accept_value(order, visible_orders, current_minute, config),
            order["promise_min"],
            order["id"],
        ),
    )

    accepted_ids = [order["id"] for order in ranked_orders[:total_capacity]]
    scheduled_ids = []
    rejected_ids = []
    for order in ranked_orders[total_capacity:]:
        if current_minute + config["max_schedule_push_min"] <= order["promise_min"]:
            scheduled_ids.append(order["id"])
        else:
            rejected_ids.append(order["id"])

    return {
        "accepted_ids": accepted_ids,
        "scheduled_ids": scheduled_ids,
        "rejected_ids": rejected_ids,
        "solver": "greedy-fallback",
    }


def solve_master_stage(orders: list[dict], riders: list[dict], current_minute: int, config: dict) -> dict:
    """Solve the accept / schedule / reject master problem."""
    global GUROBI_RUNTIME_AVAILABLE

    if not orders:
        return {"accepted_ids": [], "scheduled_ids": [], "rejected_ids": [], "solver": "empty"}

    if not GUROBI_AVAILABLE or not GUROBI_RUNTIME_AVAILABLE:
        return _fallback_master(orders, riders, current_minute, config)

    try:
        model = gp.Model("accept_schedule_reject")
        model.Params.OutputFlag = 0

        order_ids = [order["id"] for order in orders]
        order_lookup = {order["id"]: order for order in orders}
        total_capacity = sum(rider["capacity"] for rider in riders)
        visible_count = len(order_ids)

        accept = model.addVars(order_ids, vtype=GRB.BINARY, name="accept")
        schedule = model.addVars(order_ids, vtype=GRB.BINARY, name="schedule")
        reject = model.addVars(order_ids, vtype=GRB.BINARY, name="reject")

        load_ratio = visible_count / max(total_capacity, 1)
        overload_mode = load_ratio > config["load_threshold"]

        objective = gp.quicksum(
            _accept_value(order_lookup[order_id], orders, current_minute, config) * accept[order_id]
            - config["schedule_penalty"] * schedule[order_id]
            - config["rejection_penalty"] * reject[order_id]
            + (config["priority_bonus"] if overload_mode and _priority_flag(order_lookup[order_id], config) else 0.0) * accept[order_id]
            for order_id in order_ids
        )
        model.setObjective(objective, GRB.MAXIMIZE)

        for order_id in order_ids:
            order = order_lookup[order_id]
            model.addConstr(accept[order_id] + schedule[order_id] + reject[order_id] == 1, name=f"decision_{order_id}")

            if current_minute + config["max_schedule_push_min"] > order["promise_min"]:
                model.addConstr(schedule[order_id] == 0, name=f"cannot_schedule_{order_id}")

        model.addConstr(
            gp.quicksum(order_lookup[order_id]["demand"] * accept[order_id] for order_id in order_ids) <= total_capacity,
            name="vehicle_capacity_proxy",
        )

        if overload_mode:
            priority_ids = [order_id for order_id in order_ids if _priority_flag(order_lookup[order_id], config)]
            if priority_ids:
                model.addConstr(
                    gp.quicksum(accept[order_id] for order_id in priority_ids)
                    >= min(len(priority_ids), total_capacity),
                    name="overload_priority_acceptance",
                )

        model.optimize()

        accepted_ids = [order_id for order_id in order_ids if accept[order_id].X > 0.5]
        scheduled_ids = [order_id for order_id in order_ids if schedule[order_id].X > 0.5]
        rejected_ids = [order_id for order_id in order_ids if reject[order_id].X > 0.5]
        return {
            "accepted_ids": accepted_ids,
            "scheduled_ids": scheduled_ids,
            "rejected_ids": rejected_ids,
            "solver": "gurobi",
        }
    except gp.GurobiError:
        GUROBI_RUNTIME_AVAILABLE = False
        return _fallback_master(orders, riders, current_minute, config)
