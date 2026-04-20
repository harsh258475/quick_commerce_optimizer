"""TSP/VRP calculation and solving logic using Gurobi"""

from typing import Dict, List, Tuple
import gurobipy as gp  # type: ignore
from gurobipy import GRB
from config import TIME_LIMIT, MAX_ITERATIONS


class TSPCalculator:
    """Handles TSP/VRP optimization calculations"""
    
    def __init__(self, distance_matrix: List[List[float]], n_nodes: int):
        """
        Initialize calculator with distance matrix
        
        Args:
            distance_matrix: n x n distance matrix
            n_nodes: Number of nodes to solve for
        """
        self.dist = distance_matrix
        self.n = n_nodes
        self.V = list(range(n_nodes))
        self.model = None
        self.x = None
        self.iteration = 0
        
    def create_model(self) -> None:
        """Create initial Gurobi model with assignment constraints"""
        self.model = gp.Model("assignment_tsp")
        self.model.ModelSense = GRB.MINIMIZE
        self.model.Params.OutputFlag = 0
        if TIME_LIMIT:
            self.model.Params.TimeLimit = float(TIME_LIMIT)

        # Create binary variables for arcs
        self.x: Dict[Tuple[int, int], gp.Var] = {}
        for a in self.V:
            for b in self.V:
                if a == b:
                    continue
                self.x[(a, b)] = self.model.addVar(vtype=GRB.BINARY, name=f"x_{a}_{b}")

        # Objective: minimize total distance
        self.model.setObjective(
            gp.quicksum(self.dist[a][b] * self.x[(a, b)] 
                       for a in self.V for b in self.V if a != b)
        )

        # Assignment constraints: each node has out-degree 1
        for a in self.V:
            self.model.addConstr(
                gp.quicksum(self.x[(a, b)] for b in self.V if b != a) == 1, 
                name=f"out_{a}"
            )
        
        # Assignment constraints: each node has in-degree 1
        for b in self.V:
            self.model.addConstr(
                gp.quicksum(self.x[(a, b)] for a in self.V if a != b) == 1, 
                name=f"in_{b}"
            )

    def optimize(self) -> float:
        """
        Optimize the current model
        
        Returns:
            Objective value
        """
        if self.model is None:
            raise RuntimeError("Model not created. Call create_model() first.")
        
        self.model.optimize()
        
        if self.model.SolCount == 0:
            raise RuntimeError("No feasible solution found")
        
        return self.model.ObjVal
    
    def extract_solution(self) -> Tuple[List[Tuple[int, int]], List[List[int]], List[List[int]]]:
        """
        Extract arcs, all cycles, and subtours from current solution
        
        Returns:
            (selected_arcs, all_cycles, subtours)
        """
        if self.model is None or self.model.SolCount == 0:
            raise RuntimeError("No solution available")
        
        # Extract selected arcs
        arcs = sorted([(a, b) for (a, b), var in self.x.items() if var.X > 0.5])
        
        # Build next node dictionary
        nxt: Dict[int, int] = {a: b for a, b in arcs}

        # Extract cycles by following arcs
        all_cycles: List[List[int]] = []
        seen_global: set[int] = set()
        
        for start in self.V:
            if start in seen_global:
                continue
            
            cyc: List[int] = [start]
            seen_global.add(start)
            cur = start
            
            for _ in range(self.n + 1):
                cur = nxt[cur]
                cyc.append(cur)
                
                if cur == start:
                    break
                if cur in seen_global:
                    break
                seen_global.add(cur)
            
            all_cycles.append(cyc)

        # Identify depot and separate main cycle from subtours
        depot = 0
        main_cycle = next((c for c in all_cycles if depot in c[:-1]), None)
        subtours = [c for c in all_cycles if c is not main_cycle]
        
        return arcs, all_cycles, subtours
    
    def add_subtour_elimination_cut(self, cycle: List[int], name: str) -> None:
        """
        Add subtour elimination constraint (SEC) for given cycle
        
        Args:
            cycle: List of nodes in the cycle
            name: Name for the constraint
            
        Raises:
            ValueError: If cycle contains invalid nodes
        """
        if self.model is None:
            raise RuntimeError("Model not created")
        
        S = sorted(set(cycle))
        
        if not S or any(v not in self.V for v in S):
            raise ValueError(f"{name} has nodes outside 0..{self.n-1}: {S}")
        
        if len(S) <= 1:
            return
        
        self.model.addConstr(
            gp.quicksum(self.x[(i, j)] for i in S for j in S if i != j) <= len(S) - 1,
            name=name,
        )
        print(f"Added SEC cut for nodes {S}")
    
    def reset_iteration(self) -> None:
        """Reset iteration counter"""
        self.iteration = 0
    
    def next_iteration(self) -> None:
        """Increment iteration counter"""
        self.iteration += 1
