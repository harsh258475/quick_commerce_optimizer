"""Main entry point for TSP/VRP GUI application"""

import tkinter as tk
from tkinter import messagebox
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.data_loader import DataLoader
from core.calculator import TSPCalculator
from ui.dialogs import InputNodeDialog, OptionSelectionDialog, ResultsDialog
from ui.visualizer import GraphVisualizer


class TSPApp:
    """Main TSP/VRP application"""
    
    def __init__(self):
        self.n_full = None
        self.n = None
        self.option = None
        self.dist_matrix = None
        self.calculator = None
        
    def show_node_visualization(self):
        """Show nodes and distance matrix"""
        root = tk.Tk()
        root.title(f"Node Visualization - {self.n} Nodes")
        root.geometry("1200x700")

        # Header
        tk.Label(root, text=f"Distance Matrix Visualization ({self.n} nodes)", 
                font=("Arial", 14, "bold"), bg="lightblue").pack(fill=tk.X, padx=10, pady=10)

        # Main container for graph and distance matrix
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left side: Graph
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(left_frame, text="Network Graph:", font=("Arial", 10, "bold")).pack()
        
        canvas = GraphVisualizer.create_distance_graph(self.n, self.dist_matrix, master=left_frame)

        # Right side: Distance matrix table
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        tk.Label(right_frame, text="Distance Matrix", font=("Arial", 11, "bold")).pack()
        GraphVisualizer.display_distance_matrix(self.dist_matrix, self.n, right_frame)

        # Bottom panel: Info and buttons
        bottom_frame = tk.Frame(root)
        bottom_frame.pack(fill=tk.X, padx=10, pady=10)

        info_text = f"Nodes: {self.n} | Edges: {self.n * (self.n - 1)} | Color: Red=Depot, Blue=Customers"
        tk.Label(bottom_frame, text=info_text, font=("Arial", 10)).pack(side=tk.LEFT)

        result = [False]

        def on_proceed():
            result[0] = True
            root.quit()

        tk.Button(bottom_frame, text="Proceed to Options", command=on_proceed, 
                 font=("Arial", 11, "bold")).pack(side=tk.RIGHT, padx=5)

        tk.Button(bottom_frame, text="Back", command=lambda: root.quit(), 
                 font=("Arial", 11)).pack(side=tk.RIGHT, padx=5)

        root.mainloop()
        root.destroy()
        return result[0]
    
    def run(self):
        """Run the main application"""
        try:
            # Load dataset
            print("Loading dataset...")
            loader = DataLoader()
            full_dist_matrix, self.n_full = loader.load_dataset()
            print(f"Dataset loaded: {self.n_full} nodes available")
            
            # Input nodes
            print("Showing node input dialog...")
            self.n = InputNodeDialog.show(self.n_full)
            if self.n is None:
                print("Cancelled by user")
                return
            
            # Prepare distance matrix for selected nodes (reload fresh)
            loader = DataLoader()
            self.dist_matrix, _ = loader.load_dataset()
            self.dist_matrix = [row[:self.n] for row in self.dist_matrix[:self.n]]
            
            # Show visualization
            print(f"Showing visualization for {self.n} nodes...")
            if not self.show_node_visualization():
                print("Cancelled by user")
                return
            
            # Select option
            print("Showing option selection dialog...")
            self.option = OptionSelectionDialog.show()
            if self.option is None:
                print("Cancelled by user")
                return
            
            print(f"Selected Option: {self.option}")
            messagebox.showinfo("Ready", 
                f"Ready to solve with {self.n} nodes using Option {self.option}.\n\nCalculation will start in next version!")
            
        except Exception as e:
            messagebox.showerror("Error", str(e))
            print(f"Error: {e}")


def main():
    """Application entry point"""
    app = TSPApp()
    app.run()


if __name__ == "__main__":
    main()
