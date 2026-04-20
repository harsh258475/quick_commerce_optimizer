"""Graph visualization utilities using matplotlib and networkx"""

import tkinter as tk
from typing import List
import matplotlib.pyplot as plt
import matplotlib.backends.backend_tkagg as tkagg
from matplotlib.figure import Figure
import networkx as nx
from config import DEPOT_COLOR, CUSTOMER_COLOR, EDGE_COLOR, CYCLE_COLORS


class GraphVisualizer:
    """Handles graph visualization for TSP/VRP solutions"""
    
    @staticmethod
    def create_distance_graph(n_nodes: int, dist_matrix: List[List[float]], 
                             master=None) -> tk.Widget:
        """
        Create and return graph visualization for initial node display
        
        Args:
            n_nodes: Number of nodes
            dist_matrix: Distance matrix
            master: Parent widget for embedding
            
        Returns:
            Canvas widget with embedded matplotlib figure
        """
        fig = Figure(figsize=(6, 6), dpi=100)
        ax = fig.add_subplot(111)
        
        # Create directed graph
        G = nx.DiGraph()
        for i in range(n_nodes):
            G.add_node(i)
        
        # Add edges
        for i in range(n_nodes):
            for j in range(n_nodes):
                if i != j:
                    G.add_edge(i, j, weight=dist_matrix[i][j])
        
        # Create layout
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
        
        # Draw nodes
        depot_nodes = [0]
        other_nodes = [i for i in G.nodes() if i != 0]
        
        nx.draw_networkx_nodes(G, pos, nodelist=depot_nodes, node_color=DEPOT_COLOR, 
                              node_size=1000, label='Depot', ax=ax)
        nx.draw_networkx_nodes(G, pos, nodelist=other_nodes, node_color=CUSTOMER_COLOR, 
                              node_size=800, label='Customer Nodes', ax=ax)
        
        # Draw edges
        nx.draw_networkx_edges(G, pos, edge_color=EDGE_COLOR, width=1.5, 
                              alpha=0.5, arrowsize=12, arrowstyle='->', ax=ax)
        
        # Draw labels
        nx.draw_networkx_labels(G, pos, font_size=11, font_weight='bold', ax=ax)
        
        ax.legend(loc='upper left', fontsize=9)
        ax.set_title(f"Network Graph - {n_nodes} Nodes", fontsize=11, fontweight='bold')
        ax.axis('off')
        
        # Embed in tkinter if master provided
        if master:
            canvas = tkagg.FigureCanvasTkAgg(fig, master=master)
            canvas.draw()
            return canvas
        
        return fig
    
    @staticmethod
    def create_solution_graph(n_nodes: int, all_cycles: List[List[int]], 
                             master=None) -> tk.Widget:
        """
        Create and return graph visualization for solution display
        
        Args:
            n_nodes: Number of nodes
            all_cycles: All detected cycles
            master: Parent widget for embedding
            
        Returns:
            Canvas widget with embedded matplotlib figure
        """
        fig = Figure(figsize=(5, 6), dpi=100)
        ax = fig.add_subplot(111)
        
        G = nx.DiGraph()
        for i in range(n_nodes):
            G.add_node(i)
        
        edge_colors = []
        edge_list = []
        
        # Add edges from cycles with different colors
        for cycle_idx, cyc in enumerate(all_cycles):
            color = CYCLE_COLORS[cycle_idx % len(CYCLE_COLORS)]
            for i in range(len(cyc) - 1):
                u, v = cyc[i], cyc[i + 1]
                G.add_edge(u, v)
                edge_list.append((u, v))
                edge_colors.append(color)
        
        # Create layout
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
        
        # Draw nodes
        depot_nodes = [0]
        other_nodes = [i for i in G.nodes() if i != 0]
        
        nx.draw_networkx_nodes(G, pos, nodelist=depot_nodes, node_color=DEPOT_COLOR, 
                              node_size=800, label='Depot', ax=ax)
        nx.draw_networkx_nodes(G, pos, nodelist=other_nodes, node_color=CUSTOMER_COLOR, 
                              node_size=600, label='Customers', ax=ax)
        
        # Draw edges with colors
        for (u, v), color in zip(edge_list, edge_colors):
            nx.draw_networkx_edges(G, pos, [(u, v)], edge_color=color, 
                                  width=2, alpha=0.7, arrowsize=15, 
                                  arrowstyle='->', ax=ax)
        
        # Draw labels
        nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', ax=ax)
        ax.legend(loc='upper left', fontsize=8)
        ax.set_title(f"Iteration Results", fontsize=11, fontweight='bold')
        ax.axis('off')
        
        # Embed in tkinter if master provided
        if master:
            canvas = tkagg.FigureCanvasTkAgg(fig, master=master)
            canvas.draw()
            return canvas
        
        return fig
    
    @staticmethod
    def display_distance_matrix(dist_matrix: List[List[float]], n_nodes: int, 
                               parent_widget) -> None:
        """
        Display distance matrix as text in a widget with scrollbars
        
        Args:
            dist_matrix: Distance matrix
            n_nodes: Number of nodes
            parent_widget: Parent widget to display matrix in
        """
        # Create frame to hold text widget and scrollbars
        frame = tk.Frame(parent_widget)
        frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create text widget with dynamic width based on n_nodes
        text_width = max(40, 4 + n_nodes * 6)
        text_height = min(35, max(20, n_nodes + 5))
        
        # Create vertical scrollbar
        v_scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create horizontal scrollbar
        h_scrollbar = tk.Scrollbar(frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Create text widget
        matrix_text = tk.Text(frame, height=text_height, width=text_width, 
                             font=("Courier", 8), wrap=tk.NONE,
                             yscrollcommand=v_scrollbar.set,
                             xscrollcommand=h_scrollbar.set)
        matrix_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbars
        v_scrollbar.config(command=matrix_text.yview)
        h_scrollbar.config(command=matrix_text.xview)

        # Display distance matrix
        header = "    " + "  ".join(f"{i:4d}" for i in range(n_nodes))
        matrix_text.insert(tk.END, header + "\n")
        matrix_text.insert(tk.END, "-" * (len(header)) + "\n")
        
        for i in range(n_nodes):
            row_str = f"{i:3d}|"
            for j in range(n_nodes):
                row_str += f"{dist_matrix[i][j]:5.1f}"
            matrix_text.insert(tk.END, row_str + "\n")
        
        matrix_text.config(state=tk.DISABLED)
