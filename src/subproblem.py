"""Stage 2: exact VRPTW routing for accepted orders."""

from __future__ import annotations

from collections import defaultdict

from utils import travel_minutes_between

try:
    import gurobipy as gp
    from gurobipy import GRB

    GUROBI_AVAILABLE = True
except ImportError:  # pragma: no cover
    gp = None
    GRB = None
    GUROBI_AVAILABLE = False


GUROBI_RUNTIME_AVAILABLE = True


def _build_travel_times(orders: list[dict], config: dict, travel_time_matrix: dict | None = None) -> dict:
    depot = (0.0, 0.0)
    nodes = {0: depot}
    for order in orders:
        nodes[order["id"]] = (order["x"], order["y"])

    travel = {}
    for i, point_i in nodes.items():
        for j, point_j in nodes.items():
            if i == j:
                continue
            if travel_time_matrix and (i, j) in travel_time_matrix:
                travel[i, j] = travel_time_matrix[i, j]
            else:
                travel[i, j] = travel_minutes_between(point_i, point_j, config["average_speed_kmph"])
    return travel


def _greedy_fallback(
    accepted_orders: list[dict],
    riders: list[dict],
    current_minute: int,
    config: dict,
    travel_time_matrix: dict | None = None,
) -> dict:
    travel = _build_travel_times(accepted_orders, config, travel_time_matrix)
    rider_state = []
    for rider in riders:
        rider_state.append(
            {
                "rider_id": rider["id"],
                "capacity_left": rider["capacity"],
                "current_location": (rider["start_x"], rider["start_y"]),
                "current_node": 0,
                "current_minute": max(current_minute, rider["shift_start_min"]),
                "shift_end_min": rider["shift_end_min"],
                "route": [],
                "travel_minutes": 0.0,
            }
        )

    order_queue = sorted(
        accepted_orders,
        key=lambda order: (order["promise_min"], -int(order["is_premium"]), -order["basket_value"], order["id"]),
    )

    unrouted_ids = []
    stop_lookup = {}

    for order in order_queue:
        best_assignment = None
        destination = (order["x"], order["y"])
        for rider in rider_state:
            if rider["capacity_left"] < order["demand"]:
                continue

            current_node = rider.get("current_node", 0)
            leg_travel = travel[current_node, order["id"]]
            arrival = rider["current_minute"] + leg_travel
            completion = arrival + config["service_minutes"]

            if arrival > order["promise_min"] or completion > rider["shift_end_min"]:
                continue

            score = arrival + leg_travel
            if best_assignment is None or score < best_assignment["score"]:
                best_assignment = {
                    "rider": rider,
                    "arrival": arrival,
                    "completion": completion,
                    "travel": leg_travel,
                    "score": score,
                }

        if best_assignment is None:
            unrouted_ids.append(order["id"])
            continue

        rider = best_assignment["rider"]
        stop = {
            "order_id": order["id"],
            "rider_id": rider["rider_id"],
            "arrival_min": round(best_assignment["arrival"], 2),
            "travel_min": round(best_assignment["travel"], 2),
            "revenue": order["revenue"],
        }
        rider["route"].append(stop)
        rider["capacity_left"] -= order["demand"]
        rider["current_minute"] = best_assignment["completion"]
        rider["current_location"] = destination
        rider["current_node"] = order["id"]
        rider["travel_minutes"] += best_assignment["travel"]
        stop_lookup[order["id"]] = stop

    routes = []
    for rider in rider_state:
        if rider["route"]:
            routes.append(
                {
                    "rider_id": rider["rider_id"],
                    "stops": rider["route"],
                    "travel_minutes": round(rider["travel_minutes"], 2),
                }
            )

    return {
        "routes": routes,
        "unrouted_ids": unrouted_ids,
        "stop_lookup": stop_lookup,
        "travel_cost": round(sum(route["travel_minutes"] for route in routes) * config["travel_cost_per_min"], 2),
        "solver": "greedy-fallback",
    }


def _extract_routes(x: dict, t: dict, orders: list[dict], riders: list[dict], travel: dict) -> tuple[list[dict], dict]:
    customers = [order["id"] for order in orders]
    order_lookup = {order["id"]: order for order in orders}
    routes = []
    stop_lookup = {}

    for rider in riders:
        rider_id = rider["id"]
        next_map = {}
        for i in [0] + customers:
            for j in [0] + customers:
                if i == j:
                    continue
                if (i, j, rider_id) in x and x[i, j, rider_id].X > 0.5:
                    next_map[i] = j

        if 0 not in next_map:
            continue

        current = 0
        route_stops = []
        travel_minutes = 0.0
        visited_guard = set()
        while current in next_map:
            nxt = next_map[current]
            if nxt == 0 or nxt in visited_guard:
                break
            visited_guard.add(nxt)
            travel_minutes += travel[current, nxt]
            stop = {
                "order_id": nxt,
                "rider_id": rider_id,
                "arrival_min": round(t[nxt, rider_id].X, 2),
                "travel_min": round(travel[current, nxt], 2),
                "revenue": order_lookup[nxt]["revenue"],
            }
            route_stops.append(stop)
            stop_lookup[nxt] = stop
            current = nxt

        if route_stops:
            routes.append(
                {
                    "rider_id": rider_id,
                    "stops": route_stops,
                    "travel_minutes": round(travel_minutes, 2),
                }
            )

    return routes, stop_lookup


def solve_routing_stage(
    accepted_orders: list[dict],
    riders: list[dict],
    current_minute: int,
    config: dict,
    travel_time_matrix: dict | None = None,
) -> dict:
    """Solve the exact VRPTW routing subproblem for accepted orders."""
    global GUROBI_RUNTIME_AVAILABLE

    if not accepted_orders:
        return {"routes": [], "unrouted_ids": [], "stop_lookup": {}, "travel_cost": 0.0, "solver": "empty"}

    if not GUROBI_AVAILABLE or not GUROBI_RUNTIME_AVAILABLE:
        return _greedy_fallback(accepted_orders, riders, current_minute, config, travel_time_matrix)

    try:
        customers = [order["id"] for order in accepted_orders]
        nodes = [0] + customers
        rider_ids = [rider["id"] for rider in riders]
        order_lookup = {order["id"]: order for order in accepted_orders}
        rider_lookup = {rider["id"]: rider for rider in riders}
        travel = _build_travel_times(accepted_orders, config, travel_time_matrix)

        model = gp.Model("routing_vrptw")
        model.Params.OutputFlag = 0

        x = model.addVars(
            [(i, j, k) for i in nodes for j in nodes for k in rider_ids if i != j],
            vtype=GRB.BINARY,
            name="x",
        )
        z = model.addVars(customers, rider_ids, vtype=GRB.BINARY, name="assign")
        t = model.addVars(customers, rider_ids, lb=0.0, name="arrival")
        load = model.addVars(customers, rider_ids, lb=0.0, name="load")

        model.setObjective(
            gp.quicksum(travel[i, j] * config["travel_cost_per_min"] * x[i, j, k] for i, j, k in x.keys()),
            GRB.MINIMIZE,
        )

        for customer in customers:
            model.addConstr(gp.quicksum(z[customer, k] for k in rider_ids) == 1, name=f"visit_{customer}")

        for customer in customers:
            for rider_id in rider_ids:
                model.addConstr(
                    gp.quicksum(x[i, customer, rider_id] for i in nodes if i != customer) == z[customer, rider_id],
                    name=f"in_flow_{customer}_{rider_id}",
                )
                model.addConstr(
                    gp.quicksum(x[customer, j, rider_id] for j in nodes if j != customer) == z[customer, rider_id],
                    name=f"out_flow_{customer}_{rider_id}",
                )

        for rider_id in rider_ids:
            model.addConstr(
                gp.quicksum(x[0, j, rider_id] for j in customers) <= 1,
                name=f"depot_start_{rider_id}",
            )
            model.addConstr(
                gp.quicksum(x[j, 0, rider_id] for j in customers) <= 1,
                name=f"depot_end_{rider_id}",
            )
            model.addConstr(
                gp.quicksum(x[0, j, rider_id] for j in customers)
                == gp.quicksum(x[j, 0, rider_id] for j in customers),
                name=f"depot_balance_{rider_id}",
            )

        big_m_time = current_minute + config["horizon_minutes"] + max(rider["shift_end_min"] for rider in riders) + 120
        big_m_load = max(rider["capacity"] for rider in riders) + max(order["demand"] for order in accepted_orders) + 5

        for rider_id in rider_ids:
            for customer in customers:
                order = order_lookup[customer]
                rider = rider_lookup[rider_id]
                model.addConstr(
                    t[customer, rider_id] >= current_minute - big_m_time * (1 - z[customer, rider_id]),
                    name=f"time_lb_{customer}_{rider_id}",
                )
                model.addConstr(
                    t[customer, rider_id] <= order["promise_min"] + big_m_time * (1 - z[customer, rider_id]),
                    name=f"time_ub_{customer}_{rider_id}",
                )
                model.addConstr(
                    t[customer, rider_id] <= rider["shift_end_min"] + big_m_time * (1 - z[customer, rider_id]),
                    name=f"shift_ub_{customer}_{rider_id}",
                )
                model.addConstr(
                    load[customer, rider_id] >= order["demand"] * z[customer, rider_id],
                    name=f"load_lb_{customer}_{rider_id}",
                )
                model.addConstr(
                    load[customer, rider_id] <= rider["capacity"] * z[customer, rider_id],
                    name=f"load_ub_{customer}_{rider_id}",
                )

                model.addConstr(
                    t[customer, rider_id]
                    >= current_minute + travel[0, customer] - big_m_time * (1 - x[0, customer, rider_id]),
                    name=f"depot_depart_{customer}_{rider_id}",
                )

                model.addConstr(
                    t[customer, rider_id] + config["service_minutes"] + travel[customer, 0]
                    <= rider["shift_end_min"] + big_m_time * (1 - x[customer, 0, rider_id]),
                    name=f"return_shift_{customer}_{rider_id}",
                )

        for rider_id in rider_ids:
            for i in customers:
                for j in customers:
                    if i == j:
                        continue
                    model.addConstr(
                        t[j, rider_id]
                        >= t[i, rider_id] + config["service_minutes"] + travel[i, j] - big_m_time * (1 - x[i, j, rider_id]),
                        name=f"time_link_{i}_{j}_{rider_id}",
                    )
                    model.addConstr(
                        load[j, rider_id]
                        >= load[i, rider_id] + order_lookup[j]["demand"] - big_m_load * (1 - x[i, j, rider_id]),
                        name=f"load_link_{i}_{j}_{rider_id}",
                    )

        model.optimize()

        if model.Status != GRB.OPTIMAL:
            return _greedy_fallback(accepted_orders, riders, current_minute, config, travel_time_matrix)

        routes, stop_lookup = _extract_routes(x, t, accepted_orders, riders, travel)
        routed_ids = {stop["order_id"] for route in routes for stop in route["stops"]}
        travel_cost = round(model.ObjVal, 2)
        return {
            "routes": routes,
            "unrouted_ids": [order["id"] for order in accepted_orders if order["id"] not in routed_ids],
            "stop_lookup": stop_lookup,
            "travel_cost": travel_cost,
            "solver": "gurobi",
        }
    except gp.GurobiError:
        GUROBI_RUNTIME_AVAILABLE = False
        return _greedy_fallback(accepted_orders, riders, current_minute, config, travel_time_matrix)


def repair_infeasible_acceptance(
    accepted_orders: list[dict],
    riders: list[dict],
    current_minute: int,
    config: dict,
    travel_time_matrix: dict | None = None,
) -> tuple[dict, list[int]]:
    """Trim low-priority accepted orders until routing becomes feasible."""
    dropped_ids = []
    candidate_orders = sorted(
        accepted_orders,
        key=lambda order: (order["promise_min"], -int(order["is_premium"]), -order["basket_value"], order["id"]),
    )

    while candidate_orders:
        solution = solve_routing_stage(candidate_orders, riders, current_minute, config, travel_time_matrix)
        if not solution["unrouted_ids"]:
            return solution, dropped_ids

        unrouted_set = set(solution["unrouted_ids"])
        removed = None
        for order in sorted(
            candidate_orders,
            key=lambda row: (int(row["is_premium"]), row["basket_value"], -row["promise_min"], row["id"]),
        ):
            if order["id"] in unrouted_set:
                removed = order
                break

        if removed is None:
            removed = candidate_orders[-1]

        dropped_ids.append(removed["id"])
        candidate_orders = [order for order in candidate_orders if order["id"] != removed["id"]]

    return {"routes": [], "unrouted_ids": [], "stop_lookup": {}, "travel_cost": 0.0, "solver": "empty"}, dropped_ids
