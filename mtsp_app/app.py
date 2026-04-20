"""FastAPI application for quick-commerce route optimization."""

import os
import sys
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DEFAULT_ORDERS, DEFAULT_RIDERS, MAX_ORDERS_FOR_WEB
from core.mtsp_tw import MTSPTimeWindowSolver, QuickCommerceDataLoader


app = FastAPI(title="Quick Commerce Route Optimization")
app_dir = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(app_dir, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(app_dir, "templates"))

state: Dict[str, Any] = {
    "orders": [],
    "riders": [],
    "travel_time": {},
    "solution": None,
}


def load_problem_data() -> None:
    loader = QuickCommerceDataLoader()
    orders, riders, travel_time = loader.load()
    state["orders"] = orders
    state["riders"] = riders
    state["travel_time"] = travel_time


def build_travel_time_matrix() -> Dict[str, Any]:
    node_ids = [0] + [order.id for order in state["orders"]]
    matrix = []
    for source in node_ids:
        row = []
        for target in node_ids:
            row.append(0.0 if source == target else state["travel_time"].get((source, target)))
        matrix.append(row)
    return {"nodes": node_ids, "matrix": matrix}


@app.on_event("startup")
async def startup() -> None:
    load_problem_data()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not state["orders"]:
        load_problem_data()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "default_orders": DEFAULT_ORDERS,
            "default_riders": DEFAULT_RIDERS,
            "max_orders": min(MAX_ORDERS_FOR_WEB, len(state["orders"])),
            "available_orders": len(state["orders"]),
            "available_riders": len(state["riders"]),
        },
    )


@app.get("/api/problem-data")
async def problem_data():
    if not state["orders"]:
        load_problem_data()

    return {
        "success": True,
        "orders": [
            {
                "id": order.id,
                "x": order.x,
                "y": order.y,
                "demand": order.demand,
                "ready_min": order.ready_min,
                "due_min": order.due_min,
                "basket_value": order.basket_value,
                "revenue": order.revenue,
                "is_premium": order.is_premium,
            }
            for order in state["orders"]
        ],
        "riders": [
            {
                "id": rider.id,
                "capacity": rider.capacity,
                "start_x": rider.start_x,
                "start_y": rider.start_y,
                "shift_start_min": rider.shift_start_min,
                "shift_end_min": rider.shift_end_min,
            }
            for rider in state["riders"]
        ],
        "travel_time_matrix": build_travel_time_matrix(),
    }


@app.post("/api/solve-mtsp-tw")
async def solve_mtsp_tw(request: Request):
    if not state["orders"]:
        load_problem_data()

    data = await request.json()
    n_orders = int(data.get("n_orders", DEFAULT_ORDERS))
    n_riders = int(data.get("n_riders", DEFAULT_RIDERS))
    service_min = float(data.get("service_min", 2.0))
    allow_late = bool(data.get("allow_late", True))
    late_penalty = float(data.get("late_penalty", 25.0))

    max_orders = min(MAX_ORDERS_FOR_WEB, len(state["orders"]))
    if n_orders < 1 or n_orders > max_orders:
        raise HTTPException(status_code=400, detail=f"Orders must be between 1 and {max_orders}.")
    if n_riders < 1 or n_riders > len(state["riders"]):
        raise HTTPException(status_code=400, detail=f"Riders must be between 1 and {len(state['riders'])}.")
    if service_min < 0:
        raise HTTPException(status_code=400, detail="Service time cannot be negative.")
    if late_penalty < 0:
        raise HTTPException(status_code=400, detail="Late penalty cannot be negative.")

    selected_orders = state["orders"][:n_orders]
    selected_riders = state["riders"][:n_riders]

    try:
        solver = MTSPTimeWindowSolver(
            selected_orders,
            selected_riders,
            state["travel_time"],
            service_min=service_min,
            allow_late=allow_late,
            late_penalty=late_penalty,
        )
        solution = solver.solve()
        state["solution"] = solution
        return {"success": True, **solution}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        print(f"Error solving M-TSPTW: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn is required. Install it with: pip install fastapi uvicorn") from exc

    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)
