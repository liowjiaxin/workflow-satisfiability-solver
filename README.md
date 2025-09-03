# Workflow Satisfiability Problem Solvers

This project provides two Python-based solutions for the **Workflow Satisfiability Problem (WSP)**, a classic problem in access control and security. The WSP involves determining whether an assignment of users to a set of workflow steps exists that satisfies a given set of authorization and security constraints.

The project includes two distinct solver implementations: one using Google's **OR-Tools CP-SAT solver** and an alternative solution using the **Z3 SMT solver**.

## Solution Approaches

### 1. OR-Tools CP-SAT Solver (`ORTools_solution.py`)
This script models the WSP as a **Constraint Programming (CP)** problem using the OR-Tools CP-SAT solver. The implementation uses both integer-based and array-based variable representations to find a satisfying assignment.

- **Solver Used:** `ortools.sat.python.cp_model`  
- **Problem Formulation:** Constraints like **Separation of Duty (SoD)**, **Binding of Duty (BoD)**, and "at most k" are encoded as CP constraints.  
- **Evaluation:** The script evaluates performance by measuring execution time and checking for multiple solutions, saving the results in a specified directory.

### 2. Z3 SMT Solver (`Z3_alternative solution.py`)
This alternative solution models the WSP as a **Satisfiability Modulo Theories (SMT)** problem using the Z3 solver. Z3 is a powerful theorem prover and constraint solver, well-suited for problems with complex logical and mathematical constraints.

- **Solver Used:** Z3 SMT solver from the `z3` Python library.  
- **Problem Formulation:** Constraints are translated into a logical formula that Z3 attempts to satisfy.  
- **Evaluation:** Similar to the OR-Tools solution, the script measures execution time and saves the results of each instance to a file.

## How to Run

### Prerequisites
- Python  
- Google OR-Tools: `pip install ortools`  
- Z3: `pip install z3-solver`  
- Tabulate: `pip install tabulate` (for formatted output)

### File Structure
```
├── instances/ (Input directory for problem instance files)
├── solutions/ (Output directory for solution files)
├── ORTools_solution.py
├── Z3_alternative solution.py
└── README.md
```

### Execution
1. Place your WSP instance files in the `instances/` directory.  
2. Run the desired Python script:  
   - OR-Tools solution:  
     ```bash
     python ORTools_solution.py
     ```  
   - Z3 solution:  
     ```bash
     python Z3_alternative solution.py
     ```  
3. The scripts will process all instance files in the `instances/` directory, save the results in `solutions/`, and print a summary table to the console.

