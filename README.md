# quick_commerce_optimizer

Two-stage Blinkit-style quick commerce optimizer with rolling-horizon re-optimization.

## What this implements

- Stage 1 MILP: accept orders now, schedule them for later, or reject them.
- Stage 2 VRPTW: route accepted orders with rider, time-window, flow, and capacity constraints.
- Rolling horizon: re-run the decision process every minute as new orders arrive.
- Overload handling: premium users, high basket value, and clustered nearby orders get higher priority.
- KPI output: accepted rate, on-time rate, delivery time, revenue, travel time, and rider utilization.

This is an Option B style implementation of the idea from the shared chat. It uses Gurobi for both the master acceptance model and the routing subproblem when `gurobipy` and a usable license are available, and falls back gracefully when they are not.

## Project structure

```text
quick_commerce_optimizer/
|-- data/
|   |-- orders.csv
|   |-- riders.csv
|   `-- travel_time.csv
|-- src/
|   |-- main.py
|   |-- master.py
|   |-- subproblem.py
|   |-- cuts.py
|   |-- generator.py
|   |-- utils.py
|   `-- dashboard.py
|-- results/
|-- requirements.txt
`-- README.md
```

## Input data

`orders.csv`

- `id`
- `x`, `y`
- `demand`
- `created_min`
- `promise_min`
- `basket_value`
- `revenue`
- `is_premium`

`riders.csv`

- `id`
- `capacity`
- `start_x`, `start_y`
- `shift_start_min`
- `shift_end_min`

`travel_time.csv`

- `from_id`
- `to_id`
- `minutes`

The sample generator now creates:

- `50` orders
- `6` riders
- a full depot/order travel-time matrix in `travel_time.csv`

## Run

```bash
python src/main.py --sample-data
```

This regenerates sample demand and writes outputs to `results/summary.json` and `results/timeline.csv`.

To print the saved KPI dashboard again:

```bash
python src/dashboard.py
```

## Next upgrades

- Add a true travel-time matrix from maps or OSM into `travel_time.csv`.
- Carry rider positions across rolling-horizon steps instead of resetting them.
- Add lateness variables if you want soft time windows instead of hard promise constraints.
- Build a Streamlit or Plotly dashboard on top of `results/summary.json`.
