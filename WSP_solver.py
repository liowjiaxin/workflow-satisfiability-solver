# WSP_solver.py 

from ORTools_solution import Solver, save_solution
import os

def solve_instance_file(uploaded_file_path):
    """
    Runs the solver on a single uploaded instance file
    and returns the solution as a string.
    """
    # Solve the instance
    d = Solver(uploaded_file_path)
    
    # Transform into a readable output
    solution_data = (
        f"Status: {d['sat']}\n"
        f"Execution Time: {d['exe_time']}\n"
        f"Multiple Solutions: {d['mul_sol']}\n"
    )

    return solution_data
