# Quick Commerce Route Optimization

This app solves a quick-commerce route optimization problem with multiple riders and time windows.

The dataset is in `data/`:

- `orders.csv`: order coordinates, demand, release time, promised delivery time, and premium flag
- `riders.csv`: rider capacity and shift window
- `travel_time.csv`: directed travel time matrix between depot `0` and orders

## Model

The exact solver uses a MILP formulation when `gurobipy` is installed:

- each order is assigned to exactly one rider
- every used rider starts and ends at depot `0`
- rider route flow is conserved at each served order
- rider capacity is enforced
- arrival times respect order ready times
- promised delivery times are either hard constraints or soft constraints with a late-minute penalty
- rider shift end times are enforced
- time propagation constraints remove disconnected subtours

If `gurobipy` is not available, the project falls back to an append-only greedy heuristic so the app can still run for demos.

## Run

From this folder:

```bash
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 5000
```

Then open:

```text
http://127.0.0.1:5000
```

## API

`GET /api/problem-data`

Returns all orders and riders loaded from CSV.

`POST /api/solve-mtsp-tw`

Example body:

```json
{
  "n_orders": 12,
  "n_riders": 4,
  "service_min": 2,
  "allow_late": true,
  "late_penalty": 25
}
```

The response includes objective value, travel minutes, late minutes, used riders, route paths, stop arrival times, and graph edges for visualization.
