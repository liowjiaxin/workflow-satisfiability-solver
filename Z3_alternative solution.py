import os
from time import time as currenttime
from os import listdir
from os.path import isfile, join, splitext, basename
import re
import itertools

from tabulate import tabulate
from z3 import (
    Solver as Z3Solver,  # Renamed to avoid conflict with user-defined Solver
    Int,
    And,
    Or,
    Not,
    If,
    Bool,
    Sum,
    sat,
    unsat,
    Distinct,  # Corrected import (uppercase 'D')
)

class Evaluation:
    def __init__(self):
        self.number_of_instances = 0
        self.total_runtime = 0

class Instance:
    def __init__(self):
        self.number_of_steps = 0
        self.number_of_users = 0
        self.number_of_constraints = 0
        self.authorisations = []
        self.binding_of_duty = []
        self.separation_of_duty = []
        self.at_most_k = []
        self.one_team = []

def read_file(filename):
    def read_attribute(name, f):
        line = f.readline()
        match = re.match(rf"{name}:\s*(\d+)$", line.strip())
        if match:
            return int(match.group(1))
        else:
            raise Exception(f"Could not parse line '{line}'; expected the {name} attribute")

    instance = Instance()

    with open(filename) as f:
        instance.number_of_steps = read_attribute("#Steps", f)
        instance.number_of_users = read_attribute("#Users", f)
        instance.number_of_constraints = read_attribute("#Constraints", f)
        instance.authorisations = [None] * instance.number_of_users
        lines = f.read().lower().splitlines()

        for line in lines:
            if "authorisations" in line:
                user_match = re.findall(r"u\d+", line)
                if user_match:
                    user = int(user_match[0][1:])  # Extract user number
                    steps = [int(step[1:]) for step in re.findall(r"s\d+", line)]
                    instance.authorisations[user - 1] = steps
            elif "separation-of-duty" in line:
                separations = [int(sep[1:]) for sep in re.findall(r"s\d+", line)]
                # Assuming pairs of separations
                for i in range(0, len(separations), 2):
                    if i + 1 < len(separations):
                        instance.separation_of_duty.append([separations[i], separations[i+1]])
            elif "binding-of-duty" in line:
                bindings = [int(binding[1:]) for binding in re.findall(r"s\d+", line)]
                # Assuming pairs of bindings
                for i in range(0, len(bindings), 2):
                    if i + 1 < len(bindings):
                        instance.binding_of_duty.append([bindings[i], bindings[i+1]])
            elif "at-most-k" in line:
                values = line.split()
                if len(values) >= 3:
                    k = int(values[1])
                    steps = [int(v[1:]) for v in values[2:]]
                    instance.at_most_k.append([k, steps])
            elif "one-team" in line:
                steps = [int(step) for step in re.findall(r"s(\d+)", line)]
                # Corrected line: Extract numbers regardless of separator
                teams = [list(map(int, re.findall(r"\d+", team))) for team in re.findall(r"\((.*?)\)", line)]
                instance.one_team.append([teams, steps])

    return instance

def transform_output(d):
    crlf = "\r\n"
    s = "".join(kk + crlf for kk in d["sol"])
    s = d["sat"] + crlf + s + d["mul_sol"]
    s = crlf + s + crlf + str(d["exe_time"]) if "exe_time" in d else s
    return s

def solve_instance(filename, **kwargs):  # Renamed from Solver to solve_instance
    print("\n" + filename)
    instance = read_file(filename)
    print(
        f"Steps: {instance.number_of_steps}\nUsers: {instance.number_of_users}\nConstraints: {instance.number_of_constraints}"
    )

    # Initialize Z3 solver
    solver = Z3Solver()

    starttime = currenttime()

    # Define assignment variables: one Int variable per step
    assignments = [Int(f"s{i+1}") for i in range(instance.number_of_steps)]
    for var in assignments:
        solver.add(var >= 1, var <= instance.number_of_users)

    # Authorisations
    for user in range(instance.number_of_users):
        authorized_steps = instance.authorisations[user]
        if authorized_steps is not None:
            for step in range(1, instance.number_of_steps + 1):
                if step not in authorized_steps:
                    solver.add(assignments[step - 1] != (user + 1))

    # Separation of duty
    for sep in instance.separation_of_duty:
        if len(sep) >= 2:
            for i in range(len(sep)):
                for j in range(i + 1, len(sep)):
                    s1 = sep[i]
                    s2 = sep[j]
                    solver.add(assignments[s1 - 1] != assignments[s2 - 1])

    # Binding of duty
    for bind in instance.binding_of_duty:
        if len(bind) >= 2:
            for i in range(len(bind)):
                for j in range(i + 1, len(bind)):
                    s1 = bind[i]
                    s2 = bind[j]
                    solver.add(assignments[s1 - 1] == assignments[s2 - 1])

    # At most k
    for atmostk in instance.at_most_k:
        k = atmostk[0]
        steps = atmostk[1]
        # Introduce Boolean variables to indicate if a user is used
        used = [Bool(f"used_u{u+1}_k{k}") for u in range(instance.number_of_users)]
        for u in range(instance.number_of_users):
            # used[u] is True if any step is assigned to user u+1
            step_constraints = [assignments[s - 1] == (u + 1) for s in steps]
            solver.add(used[u] == Or(*step_constraints))
        # Sum of used[u] <= k
        solver.add(Sum([If(b, 1, 0) for b in used]) <= k)

    # One team
    for one_team in instance.one_team:
        teams, steps = one_team
        # For each team, create a condition that all steps are assigned to users in that team
        team_conditions = []
        for team in teams:
            team_conditions.append(And([Or(*[assignments[s - 1] == u for u in team]) for s in steps]))
        # At least one team condition must hold
        solver.add(Or(*team_conditions))

    # Trivial Step Precedence Constraint Added Here
    # Example: Step 1 precedes Step 1 (always true)
    if instance.number_of_steps >= 1:
        step_before = 1  # Step numbering starts at 1
        step_after = 1
        # This is a no-op, but included for consistency
        solver.add(assignments[step_after - 1] == assignments[step_after - 1])

    # Alternatively, add a redundant constraint between two different steps
    if instance.number_of_steps > 2:
        step_before = 1  # Step 1
        step_after = 3  # Step 3
        # Since step precedence isn't modeled with time or order, this is effectively a no-op
        solver.add(assignments[step_after - 1] == assignments[step_after - 1])

    # Initialize solution storage
    solutions = []
    multiple_solutions = False

    # First check for satisfiability
    if solver.check() == sat:
        model = solver.model()
        solution = [model.evaluate(var).as_long() for var in assignments]
        solutions.append(solution)

        # Add a constraint to exclude this solution for finding a second one
        exclude_current = Or([var != val for var, val in zip(assignments, solution)])
        solver.add(exclude_current)

        # Check for a second solution
        if solver.check() == sat:
            multiple_solutions = True

    endtime = currenttime()

    # Prepare output dictionary
    d = {
        "sat": "unsat",
        "sol": "",
        "mul_sol": "",
        "exe_time": f"{int((endtime - starttime) * 1000)}ms",
    }

    if solutions:
        d["sat"] = "sat"
        d["sol"] = [f"s{s + 1}: u{u}" for s, u in enumerate(solutions[0])]
        d["mul_sol"] = "other solutions exist" if multiple_solutions else "this is the only solution"

    return d

def save_solution(file, solution_data, output_folder):
    # Ensure the specified solutions folder exists
    os.makedirs(output_folder, exist_ok=True)

    # Derive the solution filename with 'solution_' prefix
    base_name = splitext(basename(file))[0]
    solution_file = join(output_folder, f"solution_{base_name}.txt")

    # Write the solution data to the file
    with open(solution_file, "w") as f:
        f.write(solution_data)

if __name__ == "__main__":
    evaluation = Evaluation()
    dpath = "instances"
    # Uncomment the desired instance directory
    # dpath = "instances/4-constraint"
    # dpath = "instances/3-constraint"
    # dpath = "instances/4-constraint"
    # dpath = "instances/4-constraint-hard"
    # dpath = "instances/5-constraint"
    solution_directory = "solutions1"  # Specify the directory to save solutions
    files = [
        join(dpath, f)
        for f in sorted(listdir(dpath), key=lambda x: (len(x), x))
        if isfile(join(dpath, f)) and "solution" not in f
    ]

    # List to store results for each instance
    results = []

    for file in files:
        d = solve_instance(file, silent=False)  # Updated function name
        # Extract execution time in milliseconds
        execution_time_match = re.match(r"(\d+)", d["exe_time"])
        if execution_time_match:
            execution_time = int(execution_time_match.group(1))
        else:
            execution_time = 0  # Default to 0 if not matched
        evaluation.number_of_instances += 1
        evaluation.total_runtime += execution_time

        # Collect data for each instance
        instance_result = [
            file,                    # Filename
            d["sat"],                # Solver status (sat/unsat)
            d["exe_time"],           # Execution time
            d["mul_sol"],            # Multiple solutions info
        ]

        results.append(instance_result)

        # Save the solution to the specified solutions directory
        solution_data = f"Status: {d['sat']}\nExecution Time: {d['exe_time']}\nMultiple Solutions: {d['mul_sol']}\n"
        if d["sat"] == "sat":
            solution_data += "Solution:\n" + "\n".join(d["sol"]) + "\n"
        save_solution(file, solution_data, solution_directory)

    # Print results in a table format
    headers = ["Filename", "Status", "Execution Time", "Multiple Solutions"]
    print(tabulate(results, headers=headers, tablefmt="grid", numalign="right", stralign="left"))

    # Print summary
    if evaluation.number_of_instances > 0:
        average_time = int(evaluation.total_runtime / evaluation.number_of_instances)
    else:
        average_time = 0
    print(f"\nNumber of instances: {evaluation.number_of_instances}")
    print(f"Total run time: {evaluation.total_runtime}ms")
    print(f"Average run time: {average_time}ms")
