"""Multi-salesman TSP with time windows for quick-commerce routing."""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

try:
    import gurobipy as gp  # type: ignore
    from gurobipy import GRB
except ImportError:
    gp = None
    GRB = None

from config import TIME_LIMIT


@dataclass(frozen=True)
class Order:
    id: int
    x: float
    y: float
    demand: int
    ready_min: float
    due_min: float
    basket_value: float
    revenue: float
    is_premium: bool


@dataclass(frozen=True)
class Rider:
    id: int
    capacity: int
    start_x: float
    start_y: float
    shift_start_min: float
    shift_end_min: float


class QuickCommerceDataLoader:
    """Loads quick-commerce orders, riders, and travel-time data."""

    def __init__(self, data_dir: str | None = None):
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = data_dir or os.path.join(app_dir, "data")

    def load(self) -> Tuple[List[Order], List[Rider], Dict[Tuple[int, int], float]]:
        orders = self._load_orders(os.path.join(self.data_dir, "orders.csv"))
        riders = self._load_riders(os.path.join(self.data_dir, "riders.csv"))
        travel_time = self._load_travel_time(os.path.join(self.data_dir, "travel_time.csv"))
        return orders, riders, travel_time

    @staticmethod
    def _load_orders(path: str) -> List[Order]:
        with open(path, newline="", encoding="utf-8-sig") as f:
            return [
                Order(
                    id=int(row["id"]),
                    x=float(row["x"]),
                    y=float(row["y"]),
                    demand=int(row["demand"]),
                    ready_min=float(row["created_min"]),
                    due_min=float(row["promise_min"]),
                    basket_value=float(row["basket_value"]),
                    revenue=float(row["revenue"]),
                    is_premium=bool(int(row["is_premium"])),
                )
                for row in csv.DictReader(f)
            ]

    @staticmethod
    def _load_riders(path: str) -> List[Rider]:
        with open(path, newline="", encoding="utf-8-sig") as f:
            return [
                Rider(
                    id=int(row["id"]),
                    capacity=int(row["capacity"]),
                    start_x=float(row["start_x"]),
                    start_y=float(row["start_y"]),
                    shift_start_min=float(row["shift_start_min"]),
                    shift_end_min=float(row["shift_end_min"]),
                )
                for row in csv.DictReader(f)
            ]

    @staticmethod
    def _load_travel_time(path: str) -> Dict[Tuple[int, int], float]:
        with open(path, newline="", encoding="utf-8-sig") as f:
            return {
                (int(row["from_id"]), int(row["to_id"])): float(row["minutes"])
                for row in csv.DictReader(f)
            }


class MTSPTimeWindowSolver:
    """MILP solver for mTSP/VRPTW-style delivery routing."""

    def __init__(
        self,
        orders: List[Order],
        riders: List[Rider],
        travel_time: Dict[Tuple[int, int], float],
        service_min: float = 2.0,
        allow_late: bool = True,
        late_penalty: float = 25.0,
        fixed_rider_cost: float = 0.0,
    ):
        self.orders = orders
        self.riders = riders
        self.travel_time = travel_time
        self.service_min = float(service_min)
        self.allow_late = allow_late
        self.late_penalty = float(late_penalty)
        self.fixed_rider_cost = float(fixed_rider_cost)

        self.customers = [order.id for order in orders]
        self.nodes = [0] + self.customers
        self.order_by_id = {order.id: order for order in orders}

    def solve(self) -> Dict:
        if not self.orders:
            raise ValueError("Select at least one order.")
        if not self.riders:
            raise ValueError("Select at least one rider.")
        if sum(order.demand for order in self.orders) > sum(rider.capacity for rider in self.riders):
            raise ValueError("Selected rider capacity is smaller than selected order demand.")
        if not self.allow_late:
            return self._solve_heuristic(allow_skips=True)
        if gp is None or GRB is None:
            return self._solve_heuristic()

        try:
            model = gp.Model("mtsp_time_windows")
        except Exception as exc:
            if exc.__class__.__name__ == "GurobiError":
                return self._solve_heuristic()
            raise
        model.ModelSense = GRB.MINIMIZE
        model.Params.OutputFlag = 0
        if TIME_LIMIT:
            model.Params.TimeLimit = float(TIME_LIMIT)

        rider_ids = [rider.id for rider in self.riders]
        arcs = [(i, j, k) for i in self.nodes for j in self.nodes for k in rider_ids if i != j]
        x = model.addVars(arcs, vtype=GRB.BINARY, name="x")
        y = model.addVars(self.customers, rider_ids, vtype=GRB.BINARY, name="y")
        used = model.addVars(rider_ids, vtype=GRB.BINARY, name="used")
        arrival = model.addVars(self.customers, rider_ids, lb=0.0, vtype=GRB.CONTINUOUS, name="arrival")
        late = model.addVars(self.customers, rider_ids, lb=0.0, vtype=GRB.CONTINUOUS, name="late")

        model.setObjective(
            gp.quicksum(self._travel(i, j) * x[i, j, k] for i, j, k in arcs)
            + self.fixed_rider_cost * gp.quicksum(used[k] for k in rider_ids)
            + self.late_penalty * gp.quicksum(late[i, k] for i in self.customers for k in rider_ids)
        )

        for i in self.customers:
            model.addConstr(gp.quicksum(y[i, k] for k in rider_ids) == 1, name=f"visit_{i}")

        for rider in self.riders:
            k = rider.id
            model.addConstr(
                gp.quicksum(x[0, j, k] for j in self.customers) == used[k],
                name=f"start_{k}",
            )
            model.addConstr(
                gp.quicksum(x[i, 0, k] for i in self.customers) == used[k],
                name=f"end_{k}",
            )
            model.addConstr(
                gp.quicksum(self.order_by_id[i].demand * y[i, k] for i in self.customers) <= rider.capacity,
                name=f"capacity_{k}",
            )

            for i in self.customers:
                model.addConstr(
                    gp.quicksum(x[i, j, k] for j in self.nodes if j != i) == y[i, k],
                    name=f"flow_out_{i}_{k}",
                )
                model.addConstr(
                    gp.quicksum(x[j, i, k] for j in self.nodes if j != i) == y[i, k],
                    name=f"flow_in_{i}_{k}",
                )

        big_m = self._big_m()
        for rider in self.riders:
            k = rider.id
            for i in self.customers:
                order = self.order_by_id[i]
                model.addConstr(arrival[i, k] >= order.ready_min - big_m * (1 - y[i, k]), name=f"ready_{i}_{k}")
                if self.allow_late:
                    model.addConstr(
                        arrival[i, k] <= order.due_min + late[i, k] + big_m * (1 - y[i, k]),
                        name=f"soft_due_{i}_{k}",
                    )
                    model.addConstr(late[i, k] <= big_m * y[i, k], name=f"late_off_{i}_{k}")
                else:
                    model.addConstr(
                        arrival[i, k] <= order.due_min + big_m * (1 - y[i, k]),
                        name=f"hard_due_{i}_{k}",
                    )
                    model.addConstr(late[i, k] == 0, name=f"no_late_{i}_{k}")

                model.addConstr(arrival[i, k] <= rider.shift_end_min + big_m * (1 - y[i, k]), name=f"shift_{i}_{k}")
                model.addConstr(
                    arrival[i, k] >= rider.shift_start_min + self._travel(0, i) - big_m * (1 - x[0, i, k]),
                    name=f"depot_time_{i}_{k}",
                )
                model.addConstr(
                    arrival[i, k] + self.service_min + self._travel(i, 0)
                    <= rider.shift_end_min + big_m * (1 - x[i, 0, k]),
                    name=f"return_time_{i}_{k}",
                )

            for i in self.customers:
                for j in self.customers:
                    if i == j:
                        continue
                    model.addConstr(
                        arrival[j, k]
                        >= arrival[i, k] + self.service_min + self._travel(i, j) - big_m * (1 - x[i, j, k]),
                        name=f"time_{i}_{j}_{k}",
                    )

        try:
            model.optimize()
        except Exception as exc:
            if exc.__class__.__name__ == "GurobiError":
                return self._solve_heuristic()
            raise
        if model.SolCount == 0:
            raise RuntimeError(self._status_message(model.Status))

        return self._extract_solution(model, x, y, arrival, late, used, rider_ids)

    def _extract_solution(self, model, x, y, arrival, late, used, rider_ids: Iterable[int]) -> Dict:
        routes = []
        selected_edges = []
        total_late = 0.0
        served = 0

        for rider in self.riders:
            k = rider.id
            if used[k].X < 0.5:
                routes.append(
                    {
                        "rider_id": k,
                        "used": False,
                        "capacity": rider.capacity,
                        "load": 0,
                        "distance": 0.0,
                        "distance_km": 0.0,
                        "late_minutes": 0.0,
                        "stops": [],
                        "path": [0],
                    }
                )
                continue

            next_by_node = {
                i: j
                for i in self.nodes
                for j in self.nodes
                if i != j and x[i, j, k].X > 0.5
            }
            path = [0]
            cur = 0
            for _ in range(len(self.nodes) + 1):
                nxt = next_by_node.get(cur)
                if nxt is None:
                    break
                path.append(nxt)
                selected_edges.append(
                    {
                        "source": cur,
                        "target": nxt,
                        "rider_id": k,
                        "minutes": self._travel(cur, nxt),
                        "kilometers": self._distance_km(cur, nxt),
                    }
                )
                if nxt == 0:
                    break
                cur = nxt

            stops = []
            route_late = 0.0
            route_load = 0
            route_distance = 0.0
            route_km = 0.0
            for idx in range(len(path) - 1):
                route_distance += self._travel(path[idx], path[idx + 1])
                route_km += self._distance_km(path[idx], path[idx + 1])

            for node in path:
                if node == 0:
                    continue
                order = self.order_by_id[node]
                node_late = max(0.0, late[node, k].X)
                route_late += node_late
                route_load += order.demand
                served += 1
                stops.append(
                    {
                        "order_id": node,
                        "arrival_min": round(arrival[node, k].X, 2),
                        "ready_min": order.ready_min,
                        "due_min": order.due_min,
                        "late_min": round(node_late, 2),
                        "demand": order.demand,
                        "premium": order.is_premium,
                    }
                )

            total_late += route_late
            routes.append(
                {
                    "rider_id": k,
                    "used": True,
                    "capacity": rider.capacity,
                    "load": route_load,
                    "distance": round(route_distance, 2),
                    "distance_km": round(route_km, 2),
                    "late_minutes": round(route_late, 2),
                    "stops": stops,
                    "path": path,
                }
            )

        return {
            "objective": round(model.ObjVal, 2),
            "travel_minutes": round(sum(edge["minutes"] for edge in selected_edges), 2),
            "travel_km": round(sum(edge["kilometers"] for edge in selected_edges), 2),
            "late_minutes": round(total_late, 2),
            "served_orders": served,
            "used_riders": sum(1 for route in routes if route["used"]),
            "routes": routes,
            "edges": selected_edges,
            "nodes": self._node_payload(),
            "status": "optimal" if model.Status == GRB.OPTIMAL else "time_limit_feasible",
        }

    def _solve_heuristic(self, allow_skips: bool = False) -> Dict:
        """Fallback append-only insertion heuristic used when Gurobi is unavailable."""
        unassigned = set(self.customers)
        skipped_orders = []
        route_state = {
            rider.id: {
                "rider": rider,
                "path": [0],
                "stops": [],
                "load": 0,
                "time": rider.shift_start_min,
                "travel": 0.0,
                "late": 0.0,
                "kilometers": 0.0,
            }
            for rider in self.riders
        }

        while unassigned:
            best = None
            for order_id in unassigned:
                order = self.order_by_id[order_id]
                for rider_id, route in route_state.items():
                    rider = route["rider"]
                    if route["load"] + order.demand > rider.capacity:
                        continue
                    prev = route["path"][-1]
                    raw_arrival = route["time"] + self._travel(prev, order_id)
                    arrival_time = max(raw_arrival, order.ready_min)
                    late_min = max(0.0, arrival_time - order.due_min)
                    if late_min > 0 and not self.allow_late:
                        continue
                    return_time = arrival_time + self.service_min + self._travel(order_id, 0)
                    if return_time > rider.shift_end_min:
                        continue

                    incremental = self._travel(prev, order_id) + self.late_penalty * late_min
                    if order.is_premium:
                        incremental -= 0.01
                    candidate = (incremental, arrival_time, rider_id, order_id, late_min)
                    if best is None or candidate < best:
                        best = candidate

            if best is None and allow_skips:
                for order_id in sorted(unassigned):
                    order = self.order_by_id[order_id]
                    skipped_orders.append(
                        {
                            "order_id": order_id,
                            "reason": "Cannot be delivered within the promised time window with the selected riders.",
                            "ready_min": order.ready_min,
                            "due_min": order.due_min,
                            "direct_minutes": round(self._travel(0, order_id), 2),
                        }
                    )
                break

            if best is None:
                raise RuntimeError("No feasible greedy route found. Try fewer orders, more riders, or allow late deliveries.")

            _, arrival_time, rider_id, order_id, late_min = best
            route = route_state[rider_id]
            order = self.order_by_id[order_id]
            prev = route["path"][-1]
            route["travel"] += self._travel(prev, order_id)
            route["kilometers"] += self._distance_km(prev, order_id)
            route["time"] = arrival_time + self.service_min
            route["late"] += late_min
            route["load"] += order.demand
            route["path"].append(order_id)
            route["stops"].append(
                {
                    "order_id": order_id,
                    "arrival_min": round(arrival_time, 2),
                    "ready_min": order.ready_min,
                    "due_min": order.due_min,
                    "late_min": round(late_min, 2),
                    "demand": order.demand,
                    "premium": order.is_premium,
                }
            )
            unassigned.remove(order_id)

        routes = []
        edges = []
        for rider in self.riders:
            route = route_state[rider.id]
            used = len(route["path"]) > 1
            if used:
                last = route["path"][-1]
                route["travel"] += self._travel(last, 0)
                route["kilometers"] += self._distance_km(last, 0)
                route["path"].append(0)
                for idx in range(len(route["path"]) - 1):
                    source = route["path"][idx]
                    target = route["path"][idx + 1]
                    edges.append(
                        {
                            "source": source,
                            "target": target,
                            "rider_id": rider.id,
                            "minutes": self._travel(source, target),
                            "kilometers": self._distance_km(source, target),
                        }
                    )

            routes.append(
                {
                    "rider_id": rider.id,
                    "used": used,
                    "capacity": rider.capacity,
                    "load": route["load"],
                    "distance": round(route["travel"], 2),
                    "distance_km": round(route["kilometers"], 2),
                    "late_minutes": round(route["late"], 2),
                    "stops": route["stops"],
                    "path": route["path"],
                }
            )

        total_travel = sum(edge["minutes"] for edge in edges)
        total_km = sum(edge["kilometers"] for edge in edges)
        total_late = sum(route["late_minutes"] for route in routes)
        return {
            "objective": round(total_travel + self.late_penalty * total_late, 2),
            "travel_minutes": round(total_travel, 2),
            "travel_km": round(total_km, 2),
            "late_minutes": round(total_late, 2),
            "served_orders": len(self.orders) - len(skipped_orders),
            "skipped_orders": skipped_orders,
            "used_riders": sum(1 for route in routes if route["used"]),
            "routes": routes,
            "edges": edges,
            "nodes": self._node_payload(),
            "status": "on_time_subset" if skipped_orders else "heuristic_fallback",
        }

    def _node_payload(self) -> List[Dict]:
        nodes = [{"id": 0, "label": "Depot", "type": "depot", "x": 0.0, "y": 0.0}]
        for order in self.orders:
            nodes.append(
                {
                    "id": order.id,
                    "label": f"Order {order.id}",
                    "type": "premium" if order.is_premium else "order",
                    "x": order.x,
                    "y": order.y,
                    "ready_min": order.ready_min,
                    "due_min": order.due_min,
                    "basket_value": order.basket_value,
                    "revenue": order.revenue,
                }
            )
        return nodes

    def _distance_km(self, i: int, j: int) -> float:
        source = self._coordinates(i)
        target = self._coordinates(j)
        return math.hypot(source[0] - target[0], source[1] - target[1])

    def _coordinates(self, node_id: int) -> Tuple[float, float]:
        if node_id == 0:
            return 0.0, 0.0
        order = self.order_by_id[node_id]
        return order.x, order.y

    def _travel(self, i: int, j: int) -> float:
        try:
            return self.travel_time[(i, j)]
        except KeyError as exc:
            raise ValueError(f"Missing travel time from {i} to {j}.") from exc

    def _big_m(self) -> float:
        latest_shift = max(rider.shift_end_min for rider in self.riders)
        latest_due = max(order.due_min for order in self.orders)
        max_travel = max(self._travel(i, j) for i in self.nodes for j in self.nodes if i != j)
        return latest_shift + latest_due + max_travel + self.service_min + 100.0

    @staticmethod
    def _status_message(status: int) -> str:
        if GRB is None:
            return "Gurobi is not installed."
        if status == GRB.INFEASIBLE:
            return "No feasible route found. Try fewer orders, more riders, or allow late deliveries."
        if status == GRB.TIME_LIMIT:
            return "Solver reached the time limit before finding a feasible route."
        return f"No feasible solution found. Gurobi status: {status}"
