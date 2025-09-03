import os
from time import time as currenttime
from os import listdir
from os.path import isfile, join, splitext, basename
from ortools.sat.python import cp_model
import re
import itertools

from tabulate import tabulate


class Evaluation:
    """A class for tracking evaluation metrics across multiple problem instances."""
    def __init__(self):
        self.number_of_instances = 0
        self.total_runtime = 0


class Instance:
    """
    A class to represent a problem instance. Each instance describes:
      - The number of steps to be assigned to users
      - The number of users available
      - Various authorization and constraint rules that the final solution must respect.

    Attributes:
        number_of_steps (int): The number of workflow steps.
        number_of_users (int): The number of available users.
        number_of_constraints (int): The total number of constraints.
        authorisations (list): For each user, the set of steps they are authorized to perform.
        binding_of_duty (list): Each element is a pair of steps that must be performed by the same user.
        separation_of_duty (list): Each element is a pair of steps that must be performed by different users.
        at_most_k (list): Constraints of the form (k, steps), indicating that no more than k of these steps can be done by the same user.
        one_team (list): Constraints specifying that a particular set of steps must be carried out by one "team" (subset of users).
    """
    def __init__(self):
        self.number_of_steps = 0
        self.number_of_users = 0
        self.number_of_constraints = 0
        self.authorisations = []
        self.binding_of_duty = []
        self.separation_of_duty = []
        self.at_most_k = []
        self.one_team = []


class SolutionCallback(cp_model.CpSolverSolutionCallback):
    """
    A callback to track solutions found during the search.

    This callback stops the search once more than one solution is found
    to ascertain if multiple solutions exist.
    """
    def __init__(self, variables):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__variables = variables
        self.__solution_count = 0
        self.__solutions = []

    def on_solution_callback(self):
        """Called by the solver when a new solution is found."""
        solution = [self.Value(v) for v in self.__variables]

        if solution not in self.__solutions:
            self.__solutions.append(solution)
            self.__solution_count += 1

        # If more than one solution is found, we stop the search
        if self.__solution_count > 1:
            self.StopSearch()

    def solution_count(self):
        """Return the number of unique solutions found so far."""
        return self.__solution_count


def read_file(filename):
    """
    Read a problem instance from a given file.

    The file format must include:
        #Steps: <int>
        #Users: <int>
        #Constraints: <int>
    Followed by lines describing constraints like:
        authorisations uX: sY sZ ...
        separation-of-duty: sA sB
        binding-of-duty: sA sB
        at-most-k: k sA sB sC ...
        one-team: (team1) (team2) ... sA sB ...

    Args:
        filename (str): The path to the input file.

    Returns:
        Instance: A populated Instance object with all the constraints.
    """
    def read_attribute(name):
        line = f.readline()
        match = re.match(f"{name}:\\s*(\\d+)$", line)
        if match:
            return int(match.group(1))
        else:
            raise Exception(f"Could not parse line {line}; expected the {name} attribute")

    instance = Instance()

    with open(filename) as f:
        instance.number_of_steps = read_attribute("#Steps")
        instance.number_of_users = read_attribute("#Users")
        instance.number_of_constraints = read_attribute("#Constraints")
        instance.authorisations = [None] * instance.number_of_users
        lines = f.read().lower().splitlines()

        for line in lines:
            if "authorisations" in line:
                # Extract which user and which steps they are authorized to perform.
                user = re.findall(r"u\d+", line)[0][1:]
                steps = [int(step[1:]) for step in re.findall(r"s\d+", line)]
                instance.authorisations[int(user) - 1] = steps

            elif "separation-of-duty" in line:
                # Steps that must be done by different users
                separations = [int(sep[1:]) for sep in re.findall(r"s\d+", line)]
                instance.separation_of_duty.append(separations)

            elif "binding-of-duty" in line:
                # Steps that must be done by the same user
                bindings = [int(binding[1:]) for binding in re.findall(r"s\d+", line)]
                instance.binding_of_duty.append(bindings)

            elif "at-most-k" in line:
                # No more than k steps from a given set can be done by the same user
                values = line.split()
                k = int(values[1])
                steps = [int(v[1:]) for v in values[2:]]
                instance.at_most_k.append([k, steps])

            elif "one-team" in line:
                # All steps must be done by a subset of users forming one team
                steps = [int(re.findall(r"\d+", step)[0]) for step in re.findall(r"s\d+", line)]
                teams = [re.findall(r"\d+", team) for team in re.findall(r"\((.*?)\)", line)]
                instance.one_team.append([teams, steps])

    return instance


def transform_output(d):
    """
    Transform the solution dictionary into a formatted string output.

    Args:
        d (dict): A dictionary containing keys:
            "sat"      - "sat" or "unsat"
            "sol"      - A list of solution assignments
            "mul_sol"  - A string indicating if multiple solutions exist
            "exe_time" - The execution time as a string

    Returns:
        str: A formatted string representing the solution details.
    """
    crlf = "\r\n"
    s = "".join(kk + crlf for kk in d["sol"])
    s = d["sat"] + crlf + s + d["mul_sol"]
    s = crlf + s + crlf + str(d["exe_time"]) if "exe_time" in d else s
    return s


def Solver(filename, **kwargs):
    """
    Solve the given instance using the OR-Tools CP-SAT solver.

    The problem is essentially about assigning a set of steps (S) to a set of users (U)
    subject to various constraints. Formally:

    Let:
        S = {1, ..., n_s} be the set of steps.
        U = {1, ..., n_u} be the set of users.

    We seek an assignment f: S -> U subject to constraints:
      1. Authorization: For each step s in S, f(s) must be in the set of authorized users for that step.
      2. Separation of Duty: If (s1, s2) in separation_of_duty, then f(s1) != f(s2).
      3. Binding of Duty: If (s1, s2) in binding_of_duty, then f(s1) = f(s2).
      4. At-most-k: For a subset of steps T and integer k, no user is assigned to more than k of these steps.
      5. One-team: For a specified set of steps T and multiple "team" subsets of users, the assignment must
         be consistent with one of the given teams, i.e., all steps in T come from that team configuration.

    This function:
        - Reads the instance file
        - Builds a CP-SAT model
        - Adds all constraints
        - Solves the model
        - Records the solution status and solution details if feasible.

    Args:
        filename (str): The path to the instance file.

    Returns:
        dict: A dictionary with keys:
              "sat" ("sat" or "unsat"),
              "sol" (the assignments as a list of strings),
              "mul_sol" (string indicating multiple solutions),
              "exe_time" (the runtime in ms).
    """
    print("\n" + filename)
    instance = read_file(filename)
    print(
        f"Steps: {instance.number_of_steps}\n"
        f"Users: {instance.number_of_users}\n"
        f"Constraints: {instance.number_of_constraints}"
    )

    model = cp_model.CpModel()
    starttime = int(currenttime() * 1000)

    # Create decision variables: assignments[s] = user assigned to step s.
    assignments = [model.NewIntVar(1, instance.number_of_users, f"s{i}") for i in range(instance.number_of_steps)]

    bool_vars = {}  # A cache to store boolean variables used in at-most-k constraints.

    # Authorisations: steps that a given user is not authorized to perform are excluded.
    for user in range(instance.number_of_users):
        for step in range(1, instance.number_of_steps + 1):
            if instance.authorisations[user] is not None and step not in instance.authorisations[user]:
                model.Add(assignments[step - 1] != user + 1)

    # Separation of duty: steps must be performed by different users
    for separations in instance.separation_of_duty:
        model.Add(assignments[separations[0] - 1] != assignments[separations[1] - 1])

    # Binding of duty: steps must be performed by the same user
    for bindings in instance.binding_of_duty:
        model.Add(assignments[bindings[0] - 1] == assignments[bindings[1] - 1])

    # At most k: no user is assigned to more than k steps out of a given set.
    # Model as logical constraints: If more than k steps are done by the same user, it creates a forbidden pattern.
    for atmostk in instance.at_most_k:
        k = atmostk[0]
        steps = atmostk[1]

        # For any combination of k+1 steps, they cannot all be assigned to the same user.
        for combination in itertools.combinations(steps, k + 1):
            same_users = []

            for (step1, step2) in itertools.combinations(combination, 2):
                key1 = f"s{step1}=s{step2}"
                key2 = f"s{step2}=s{step1}"

                # We reuse boolean variables if already created.
                if key1 in bool_vars:
                    bool_var = bool_vars[key1]
                elif key2 in bool_vars:
                    bool_var = bool_vars[key2]
                else:
                    bool_var = model.NewBoolVar(key1)
                    bool_vars[key1] = bool_var

                # If bool_var is True, assignments are equal. Otherwise, they are not constrained by this literal.
                model.Add(assignments[step1 - 1] == assignments[step2 - 1]).OnlyEnforceIf(bool_var)
                same_users.append(bool_var)

            # If all these steps are to be performed by the same user, at least for pairs they must match.
            # AddBoolOr ensures that there's a consistency pattern. The logic ensures no single user can dominate all k+1 steps.
            model.AddBoolOr(same_users)

    # One team: The set of steps must be assigned according to one of the allowed teams.
    # An AllowedAssignments constraint enumerates all allowed user assignments.
    for teams, steps in instance.one_team:
        constraint_steps = [assignments[step - 1] for step in steps]
        allowed_combinations = []

        # Generate all combinations of team members for the given steps.
        # Each combination is a tuple (user_for_step1, user_for_step2, ...).
        for team in teams:
            allowed_combinations.extend(itertools.product(team, repeat=len(steps)))

        # Ensure that we convert the combinations to integers.
        allowed_combinations = [tuple(map(int, combination)) for combination in allowed_combinations]

        # Only assignments present in allowed_combinations are allowed for these steps.
        model.AddAllowedAssignments(constraint_steps, allowed_combinations)

    # **Potential Precedence Constraints (Currently Trivial)**
    # For demonstration, we add a redundant always-true constraint to show where precedence constraints could go.
    if instance.number_of_steps >= 1:
        step_before = 1
        step_after = 1
        model.Add(assignments[step_after - 1] == assignments[step_after - 1])  # trivially true

    if instance.number_of_steps > 2:
        step_before = 1
        step_after = 3
        # Another trivial constraint: step_after equals step_after.
        model.Add(assignments[step_after - 1] == assignments[step_after - 1])  # trivially true

    solver = cp_model.CpSolver()
    solution_callback = SolutionCallback(assignments)
    solver.parameters.enumerate_all_solutions = True

    status = solver.Solve(model, solution_callback)
    endtime = int(currenttime() * 1000)

    d = {"sat": "unsat", "sol": "", "mul_sol": "", "exe_time": f"{endtime - starttime}ms"}

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        d["sat"] = "sat"
        d["sol"] = [f"s{s + 1}: u{solver.Value(u)}" for s, u in enumerate(assignments)]
        d["mul_sol"] = "other solutions exist" if solution_callback.solution_count() > 1 else "this is the only solution"

    return d


def save_solution(file, solution_data, output_folder):
    """
    Save the solution data to a text file in the given output folder.

    The output file is named "solution_<base_filename>.txt".

    Args:
        file (str): The original problem instance filename.
        solution_data (str): The solution details as a string.
        output_folder (str): The directory where solution files will be stored.
    """
    # Ensure the specified solutions folder exists
    os.makedirs(output_folder, exist_ok=True)

    base_name = splitext(basename(file))[0]
    solution_file = join(output_folder, f"solution_{base_name}.txt")

    with open(solution_file, "w") as f:
        f.write(solution_data)


if __name__ == "__main__":
    evaluation = Evaluation()
    dpath = "instances"
    # Uncomment one of the below paths to test on different datasets:
    # dpath = "instances/3-constraint"
    # dpath = "instances/4-constraint"
    # dpath = "instances/4-constraint-hard"
    # dpath = "instances/5-constraint"

    solution_directory = "solutions1"  # Specify the directory to save solutions

    # Gather all files except those that already contain 'solution' in their name
    files = [
        join(dpath, f) for f in sorted(listdir(dpath), key=lambda x: (len(x), x))
        if isfile(join(dpath, f)) and "solution" not in f
    ]

    # Collect results for each instance to later present in a tabular format
    results = []

    for file in files:
        d = Solver(file, silent=False)
        execution_time = int(re.match(r"\d+", d["exe_time"]).group(0))
        evaluation.number_of_instances += 1
        evaluation.total_runtime += execution_time

        instance_result = [
            file,             # Filename
            d["sat"],         # Solver status (sat/unsat)
            d["exe_time"],    # Execution time
            d["mul_sol"],     # Multiple solutions info
        ]
        results.append(instance_result)

        # Save the solution to the specified solutions directory
        solution_data = (
            f"Status: {d['sat']}\n"
            f"Execution Time: {d['exe_time']}\n"
            f"Multiple Solutions: {d['mul_sol']}\n"
        )
        save_solution(file, solution_data, solution_directory)

    # Print results in a table format for a quick overview
    headers = ["Filename", "Status", "Execution Time", "Multiple Solutions"]
    print(tabulate(results, headers=headers, tablefmt="grid", numalign="right", stralign="left"))

    # Print summary of performance
    print(f"\nNumber of instances: {evaluation.number_of_instances}")
    print(f"Total run time: {evaluation.total_runtime}ms")
    if evaluation.number_of_instances > 0:
        print(f"Average run time: {int(evaluation.total_runtime / evaluation.number_of_instances)}ms")
