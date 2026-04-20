"""GUI dialogs for TSP/VRP solver"""

import ast
import tkinter as tk
from tkinter import simpledialog, messagebox
from typing import Dict, List, Optional
from config import WINDOW_GEOMETRY, DEFAULT_NODES


class InputNodeDialog:
    """Dialog for inputting number of nodes"""
    
    @staticmethod
    def show(n_full: int) -> Optional[int]:
        """
        Show input nodes dialog
        
        Args:
            n_full: Maximum available nodes
            
        Returns:
            Number of nodes selected, or None if cancelled
        """
        root = tk.Tk()
        root.title("Enter Number of Nodes")
        root.geometry(WINDOW_GEOMETRY["input"])

        tk.Label(root, text="Enter number of nodes to visualize:", 
                font=("Arial", 12, "bold")).pack(pady=20)
        
        nodes_entry = tk.Entry(root, width=20, font=("Arial", 14))
        nodes_entry.insert(0, str(DEFAULT_NODES))
        nodes_entry.pack(pady=10)

        tk.Label(root, text=f"(Available: 2 to 9 nodes)", font=("Arial", 10)).pack(pady=5)

        result = [None]

        def on_submit():
            try:
                nodes_val = int(nodes_entry.get())
                if nodes_val < 2 or nodes_val > 9:
                    raise ValueError(f"Please enter a number between 2 and 9")
                result[0] = nodes_val
                root.quit()
            except ValueError as e:
                messagebox.showerror("Invalid input", str(e))

        tk.Button(root, text="Next", command=on_submit, 
                 font=("Arial", 12, "bold"), width=15).pack(pady=15)

        root.mainloop()
        root.destroy()
        return result[0]


class OptionSelectionDialog:
    """Dialog for selecting solving option"""
    
    @staticmethod
    def show() -> Optional[int]:
        """
        Show option selection dialog
        
        Returns:
            Selected option (0, 1, or 2), or None if cancelled
        """
        root = tk.Tk()
        root.title("Select Solving Option")
        root.geometry("850x750")

        tk.Label(root, text="Select subtour handling option:", 
                font=("Arial", 11, "bold")).pack(pady=10)

        option_text = """Option 0: No subtour elimination constraints
- Just print the subtours from assignment relaxation
- Fastest to implement

Option 1: Manually add subtour elimination constraints
- Enter subtours in next screen after seeing results
- Can target specific subtours

Option 2: Automatically detect and eliminate all subtours
- Fully automated, ensures convergence to single tour"""

        text_widget = tk.Text(root, height=7, width=100, wrap=tk.WORD)
        text_widget.insert(tk.END, option_text)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(pady=10, padx=10)

        selected_option = tk.IntVar(value=-1)

        radio_frame = tk.Frame(root)
        radio_frame.pack(pady=5)
        tk.Radiobutton(radio_frame, text="Option 0", variable=selected_option, value=0).pack(anchor=tk.W)
        tk.Radiobutton(radio_frame, text="Option 1", variable=selected_option, value=1).pack(anchor=tk.W)
        tk.Radiobutton(radio_frame, text="Option 2", variable=selected_option, value=2).pack(anchor=tk.W)

        result = [None]

        def on_submit():
            if selected_option.get() < 0:
                messagebox.showerror("Error", "Please select an option")
                return
            result[0] = selected_option.get()
            root.quit()

        tk.Button(root, text="Submit", command=on_submit, 
                 font=("Arial", 12, "bold"), width=20).pack(pady=15)

        root.mainloop()
        root.destroy()
        return result[0]


class ResultsDialog:
    """Dialog for showing results and optional subtour input"""
    
    @staticmethod
    def show(iteration: int, objective: float, arcs: List, 
             all_cycles: List, subtours: List, option: int, 
             canvas_widget=None) -> Dict:
        """
        Show results dialog with graph
        
        Args:
            iteration: Current iteration number
            objective: Current objective value
            arcs: Selected arcs in solution
            all_cycles: All detected cycles
            subtours: Detected subtours (excluding main cycle)
            option: Current solving option (0, 1, or 2)
            canvas_widget: Matplotlib canvas widget to embed
            
        Returns:
            Dictionary with {continue: bool, subtours: List or None}
        """
        root = tk.Tk()
        root.title(f"TSP Iteration {iteration} Results")
        root.geometry(WINDOW_GEOMETRY["results"])

        # Header
        header_text = f"Iteration {iteration} | Objective: {objective:.2f} | Subtours: {len(subtours)}"
        tk.Label(root, text=header_text, font=("Arial", 12, "bold"), 
                bg="lightblue").pack(fill=tk.X, padx=10, pady=10)

        # Left panel: Info
        left_frame = tk.Frame(root)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(left_frame, text="Selected Arcs:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        arcs_text = tk.Text(left_frame, height=5, width=40, wrap=tk.WORD)
        arcs_text.insert(tk.END, str(arcs))
        arcs_text.config(state=tk.DISABLED)
        arcs_text.pack(fill=tk.BOTH, expand=True, pady=5)

        tk.Label(left_frame, text="Subtours Found:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 0))
        subtours_text = tk.Text(left_frame, height=8, width=40, wrap=tk.WORD)
        for i, cyc in enumerate(subtours):
            subtours_text.insert(tk.END, f"Route {i+1}: {' -> '.join(map(str, cyc))}\n")
        subtours_text.config(state=tk.DISABLED)
        subtours_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Right panel: Graph
        right_frame = tk.Frame(root)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(right_frame, text="Solution Graph:", font=("Arial", 10, "bold")).pack()
        
        if canvas_widget:
            canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Bottom panel: Action buttons
        bottom_frame = tk.Frame(root)
        bottom_frame.pack(fill=tk.X, padx=10, pady=10)

        result = {"continue": False, "subtours": None}

        if option == 1 and len(subtours) > 0:
            tk.Label(bottom_frame, text="Enter manual subtours for next iteration:", 
                    font=("Arial", 9)).pack(anchor=tk.W)
            subtour_entry = tk.Entry(bottom_frame, width=80, font=("Arial", 9))
            subtour_entry.insert(0, "[[0,5,0],[1,3,1]]")
            subtour_entry.pack(fill=tk.X, pady=5)

            def on_continue():
                try:
                    subtour_str = subtour_entry.get().strip()
                    if subtour_str:
                        manual_subs = ast.literal_eval(subtour_str)
                        if not isinstance(manual_subs, list) or not all(isinstance(c, list) for c in manual_subs):
                            raise ValueError("Invalid format")
                        result["subtours"] = manual_subs
                    result["continue"] = True
                    root.quit()
                except ValueError as e:
                    messagebox.showerror("Invalid input", f"Invalid subtour format: {e}")

            tk.Button(bottom_frame, text="Continue with Subtours", command=on_continue, 
                     font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        else:
            def on_continue():
                result["continue"] = True
                root.quit()

            tk.Button(bottom_frame, text="Continue", command=on_continue, 
                     font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)

        def on_stop():
            result["continue"] = False
            root.quit()

        tk.Button(bottom_frame, text="Stop", command=on_stop, 
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=5)

        root.mainloop()
        root.destroy()
        return result
