"""Configuration and constants for TSP/VRP solver"""

import os

# Dataset configuration
DATASET_FILENAME = "phub25_dataset.txt"

# Try multiple possible locations for dataset
possible_paths = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), DATASET_FILENAME),  # In tsp_app/
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), DATASET_FILENAME),  # In parent/
]

# Use the first path that exists
DATASET_PATH = None
for path in possible_paths:
    if os.path.exists(path):
        DATASET_PATH = path
        break

# If none found, use default (will be caught in DataLoader)
if DATASET_PATH is None:
    DATASET_PATH = possible_paths[1]  # Parent directory is more common

# Web server configuration
FLASK_HOST = '127.0.0.1'
FLASK_PORT = 5000
FLASK_DEBUG = True

# GUI configuration (for legacy GUI app)
WINDOW_GEOMETRY = {
    "input": "400x200",
    "visualization": "1200x700",
    "results": "950x800"
}

# Node configuration
DEFAULT_NODES = 7
MIN_NODES = 2
DEFAULT_ORDERS = 12
DEFAULT_RIDERS = 4
MAX_ORDERS_FOR_WEB = 24

# Solver configuration
TIME_LIMIT = 30
MAX_ITERATIONS = 200

# Graph visualization colors
DEPOT_COLOR = "red"
CUSTOMER_COLOR = "lightblue"
EDGE_COLOR = "gray"
CYCLE_COLORS = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']

