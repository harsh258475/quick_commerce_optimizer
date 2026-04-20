"""Configuration and constants for TSP/VRP solver."""

import os

DATASET_FILENAME = "phub25_dataset.txt"

possible_paths = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), DATASET_FILENAME),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), DATASET_FILENAME),
]

DATASET_PATH = None
for path in possible_paths:
    if os.path.exists(path):
        DATASET_PATH = path
        break

if DATASET_PATH is None:
    DATASET_PATH = possible_paths[1]

FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
FLASK_DEBUG = True

WINDOW_GEOMETRY = {
    "input": "400x200",
    "visualization": "1200x700",
    "results": "950x800",
}

DEFAULT_NODES = 7
MIN_NODES = 2
DEFAULT_ORDERS = 6
DEFAULT_RIDERS = 2
MAX_ORDERS_FOR_WEB = 50

TIME_LIMIT = 30
MAX_ITERATIONS = 200

DEPOT_COLOR = "red"
CUSTOMER_COLOR = "lightblue"
EDGE_COLOR = "gray"
CYCLE_COLORS = ["red", "blue", "green", "orange", "purple", "brown", "pink", "gray", "olive", "cyan"]
