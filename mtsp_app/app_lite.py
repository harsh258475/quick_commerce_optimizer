"""Lightweight HTTP server for TSP/VRP solver - uses only Python built-ins"""

import json
import mimetypes
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from threading import Thread
import webbrowser
import time
import ast

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.data_loader import DataLoader
from core.calculator import TSPCalculator
from config import DEFAULT_NODES, FLASK_PORT

# Global state
solver_state = {
    'n_full': None,
    'n': None,
    'option': None,
    'dist_matrix': None,
    'calculator': None,
    'iteration': 0,
    'solution': None,
    'all_cycles': [],
    'subtours': [],
    'arcs': [],
    'objective': None
}

# Load dataset on startup
try:
    loader = DataLoader()
    dist, n_full = loader.load_dataset()
    solver_state['dist_matrix'] = dist
    solver_state['n_full'] = n_full
    print(f"✓ Dataset loaded: {n_full} nodes available")
except Exception as e:
    print(f"✗ Error loading dataset: {e}")
    sys.exit(1)


class TSPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for TSP API and static files"""
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # API requests
        if path == '/api/get-graph-data':
            self.handle_graph_data()
        # Static files
        elif path == '/':
            self.serve_file('templates/index.html', 'text/html')
        elif path.startswith('/static/'):
            file_path = path[1:]  # Remove leading /
            content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
            self.serve_file(file_path, content_type)
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON", 400)
            return
        
        # Route to appropriate handler
        try:
            if path == '/api/load-nodes':
                self.handle_load_nodes(data)
            elif path == '/api/set-option':
                self.handle_set_option(data)
            elif path == '/api/solve-iteration':
                self.handle_solve_iteration()
            elif path == '/api/add-subtours':
                self.handle_add_subtours(data)
            elif path == '/api/add-auto-subtours':
                self.handle_add_auto_subtours()
            else:
                self.send_error(404, "Not Found")
        except Exception as e:
            self.send_json_error(str(e), 500)
    
    def serve_file(self, file_path, content_type):
        """Serve a static file"""
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        
        if not os.path.exists(full_path):
            self.send_error(404, "File not found")
            return
        
        try:
            with open(full_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, str(e))
    
    def send_json(self, data):
        """Send JSON response"""
        response = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response)
    
    def send_json_error(self, error, status_code=400):
        """Send JSON error response"""
        response = json.dumps({'success': False, 'error': error}).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.end_headers()
        self.wfile.write(response)
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass
    
    # API Handlers
    def handle_load_nodes(self, data):
        """Load and prepare nodes"""
        n_nodes = int(data.get('n_nodes', DEFAULT_NODES))
        
        if n_nodes < 2 or n_nodes > 9:
            self.send_json_error(f'Nodes must be between 2 and 9', 400)
            return
        
        solver_state['n'] = n_nodes
        
        # Prepare distance matrix
        full_dist = solver_state['dist_matrix']
        dist_matrix = [row[:n_nodes] for row in full_dist[:n_nodes]]
        solver_state['dist_matrix'] = dist_matrix
        
        # Create node data
        nodes = list(range(n_nodes))
        distances = {}
        
        for i in range(n_nodes):
            for j in range(n_nodes):
                if i != j:
                    distances[f"{i}-{j}"] = dist_matrix[i][j]
        
        self.send_json({
            'success': True,
            'nodes': nodes,
            'distances': distances,
            'n_nodes': n_nodes
        })
    
    def handle_set_option(self, data):
        """Set solving option"""
        option = int(data.get('option', -1))
        
        if option not in [0, 1, 2]:
            self.send_json_error('Invalid option', 400)
            return
        
        solver_state['option'] = option
        
        # Create calculator
        solver_state['calculator'] = TSPCalculator(solver_state['dist_matrix'], solver_state['n'])
        solver_state['calculator'].create_model()
        solver_state['iteration'] = 0
        
        self.send_json({
            'success': True,
            'message': f'Option {option} selected. Ready to solve.',
            'option': option
        })
    
    def handle_solve_iteration(self):
        """Solve one iteration"""
        if solver_state['calculator'] is None:
            self.send_json_error('Solver not initialized', 400)
            return
        
        calc = solver_state['calculator']
        
        # Optimize
        objective = calc.optimize()
        
        # Extract solution
        arcs, all_cycles, subtours = calc.extract_solution()
        
        # Store results
        solver_state['iteration'] += 1
        solver_state['objective'] = objective
        solver_state['arcs'] = arcs
        solver_state['all_cycles'] = all_cycles
        solver_state['subtours'] = subtours
        
        # Prepare response
        arcs_display = [f"{a} → {b}" for a, b in arcs]
        subtours_display = [f"Route {i+1}: {' → '.join(map(str, cyc[:-1]))}" for i, cyc in enumerate(subtours)]
        
        # Check if solved
        is_solved = len(subtours) == 0
        
        self.send_json({
            'success': True,
            'iteration': solver_state['iteration'],
            'objective': objective,
            'arcs': arcs_display,
            'all_cycles': all_cycles,
            'subtours': subtours_display,
            'num_subtours': len(subtours),
            'is_solved': is_solved,
            'option': solver_state['option']
        })
    
    def handle_add_subtours(self, data):
        """Add manual subtours"""
        if solver_state['calculator'] is None:
            self.send_json_error('Solver not initialized', 400)
            return
        
        subtours_str = data.get('subtours', '')
        
        if not subtours_str.strip():
            self.send_json_error('No subtours provided', 400)
            return
        
        # Parse subtours
        try:
            subtours = ast.literal_eval(subtours_str)
            if not isinstance(subtours, list) or not all(isinstance(c, list) for c in subtours):
                raise ValueError("Invalid format")
        except Exception as e:
            self.send_json_error(f'Invalid subtour format: {e}', 400)
            return
        
        # Add SEC cuts
        calc = solver_state['calculator']
        for idx, cycle in enumerate(subtours):
            calc.add_subtour_elimination_cut(cycle, name=f"manual_subtour_{solver_state['iteration']}_{idx}")
        
        self.send_json({
            'success': True,
            'message': f'Added {len(subtours)} manual subtour constraints'
        })
    
    def handle_add_auto_subtours(self):
        """Add automatic subtours"""
        if solver_state['calculator'] is None:
            self.send_json_error('Solver not initialized', 400)
            return
        
        calc = solver_state['calculator']
        subtours = solver_state['subtours']
        
        # Add SEC cuts
        for k, cyc in enumerate(subtours):
            calc.add_subtour_elimination_cut(cyc[:-1], name=f"subtour_{solver_state['iteration']}_{k}")
        
        self.send_json({
            'success': True,
            'message': f'Added {len(subtours)} automatic subtour constraints'
        })
    
    def handle_graph_data(self):
        """Get graph data for current solution"""
        n = solver_state['n']
        all_cycles = solver_state['all_cycles']
        dist_matrix = solver_state['dist_matrix']
        
        # Create nodes data
        nodes_data = []
        for i in range(n):
            node_type = 'depot' if i == 0 else 'customer'
            nodes_data.append({
                'id': i,
                'type': node_type,
                'label': f'Node {i}'
            })
        
        # Create edges data
        edges_data = []
        colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
        
        for cycle_idx, cycle in enumerate(all_cycles):
            color = colors[cycle_idx % len(colors)]
            for i in range(len(cycle) - 1):
                u, v = cycle[i], cycle[i + 1]
                distance = dist_matrix[u][v]
                edges_data.append({
                    'source': u,
                    'target': v,
                    'weight': distance,
                    'color': color,
                    'cycle_id': cycle_idx
                })
        
        self.send_json({
            'success': True,
            'nodes': nodes_data,
            'edges': edges_data
        })


def run_server():
    """Run the HTTP server"""
    server = HTTPServer(('127.0.0.1', FLASK_PORT), TSPHandler)
    print(f"\n✓ Server started at http://127.0.0.1:{FLASK_PORT}")
    print(f"✓ Opening browser...")
    
    # Open browser after a short delay
    def open_browser():
        time.sleep(1)
        webbrowser.open(f'http://127.0.0.1:{FLASK_PORT}')
    
    browser_thread = Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Server stopped")
        server.shutdown()


if __name__ == '__main__':
    print("╔════════════════════════════════════════╗")
    print("║   TSP/VRP Solver - Lightweight Web     ║")
    print("║   (No Flask - Pure Python)             ║")
    print("╚════════════════════════════════════════╝\n")
    
    run_server()
