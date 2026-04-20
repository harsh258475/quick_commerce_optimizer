"""Data loader for TSP/VRP datasets"""

import ast
import os
from typing import List, Tuple
from config import DATASET_PATH


class DataLoader:
    """Load and parse TSP/VRP datasets from text files"""
    
    @staticmethod
    def load_dataset(dataset_txt: str | None = None, distance_matrix_index: int = 0) -> Tuple[List[List[float]], int]:
        """
        Load distance matrix from dataset file
        
        Args:
            dataset_txt: Path to dataset file (uses default if None)
            distance_matrix_index: Which matrix to extract (0, 1, 2, etc.)
        
        Returns:
            (distance_matrix, n_full) - The distance matrix and total nodes available
        
        Raises:
            FileNotFoundError: If dataset file not found
            ValueError: If no valid matrices found
            IndexError: If matrix index out of range
        """
        dataset_txt = dataset_txt or DATASET_PATH
        
        if not os.path.exists(dataset_txt):
            raise FileNotFoundError(f"Missing dataset file: {dataset_txt}")

        with open(dataset_txt, "r", encoding="utf-8-sig") as f:
            content = f.read()

        matrices: List[List[List[float]]] = DataLoader._extract_matrices(content)

        if not matrices:
            raise ValueError(f"No valid square matrix found in: {dataset_txt}")

        if not (0 <= distance_matrix_index < len(matrices)):
            raise IndexError(f"distance_matrix_index={distance_matrix_index} out of range (available: {len(matrices)})")

        dist = matrices[distance_matrix_index]
        n_full = len(dist)
        return dist, n_full
    
    @staticmethod
    def _extract_matrices(content: str) -> List[List[List[float]]]:
        """
        Extract all valid square matrices from text content
        
        Args:
            content: Raw text content containing matrices
            
        Returns:
            List of valid distance matrices
        """
        matrices: List[List[List[float]]] = []
        i = 0
        
        while i < len(content):
            if content[i] != "[":
                i += 1
                continue
            
            # Find matching closing bracket
            depth = 0
            j = i
            while j < len(content):
                if content[j] == "[":
                    depth += 1
                elif content[j] == "]":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1

            chunk = content[i:j].strip()
            i = j
            
            # Try to parse as Python literal
            try:
                obj = ast.literal_eval(chunk)
            except Exception:
                continue
            
            # Validate matrix structure
            if DataLoader._is_valid_matrix(obj):
                mtx = [[float(v) for v in r] for r in obj]
                matrices.append(mtx)

        return matrices
    
    @staticmethod
    def _is_valid_matrix(obj) -> bool:
        """
        Validate if object is a valid square numeric matrix
        
        Args:
            obj: Object to validate
            
        Returns:
            True if valid matrix, False otherwise
        """
        if not isinstance(obj, list) or not obj:
            return False
        
        if not all(isinstance(r, list) for r in obj):
            return False
        
        if not all(r and all(isinstance(v, (int, float)) for v in r) for r in obj):
            return False
        
        n = len(obj)
        if n < 2:
            return False
        
        if not all(len(r) == n for r in obj):
            return False
        
        return True
