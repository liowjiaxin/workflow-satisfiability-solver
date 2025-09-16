import streamlit as st
from ORTools_solution import Solver, transform_output
import tempfile
import os
from tabulate import tabulate
import pandas as pd

# --- CONFIG ---
INSTANCES_FOLDER = "instances"  # preloaded instances folder

st.set_page_config(page_title="Workflow Satisfiability Solver", layout="wide")
st.title("Workflow Satisfiability Solver (WSP)")

st.markdown("""
Upload one or multiple workflow instance files (TXT format), or select from the preloaded instances below.
""")

# --- List preloaded instances ---
preloaded_files = [
    f for f in os.listdir(INSTANCES_FOLDER)
    if os.path.isfile(os.path.join(INSTANCES_FOLDER, f)) and f.lower().endswith(".txt")
]

selected_preloaded = st.multiselect(
    "Select preloaded instance(s) to solve",
    options=preloaded_files
)

# --- File uploader ---
uploaded_files = st.file_uploader(
    "Upload WSP instance file(s)", type="txt", accept_multiple_files=True
)

# Combine both uploaded and preloaded selections
instances_to_solve = []

# Handle uploaded files
tmp_paths = []
if uploaded_files:
    for uploaded_file in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name
            tmp_paths.append(tmp_path)
            instances_to_solve.append((uploaded_file.name, tmp_path))

# Handle preloaded selections
for fname in selected_preloaded:
    file_path = os.path.join(INSTANCES_FOLDER, fname)
    instances_to_solve.append((fname, file_path))

# --- Solve button ---
if instances_to_solve:
    if st.button("Solve"):
        solutions = []
        results_table = []

        for fname, path in instances_to_solve:
            # Solve the instance
            solution_data = Solver(path)

            # Prepare readable output
            solution_str = transform_output(solution_data)
            solutions.append((fname, solution_str))

            # Collect results for table
            results_table.append([
                fname,
                solution_data["sat"],
                solution_data["exe_time"],
                solution_data["mul_sol"]
            ])

        # Display results in a dataframe
        df = pd.DataFrame(results_table, columns=["Filename", "Status", "Execution Time", "Multiple Solutions"])
        st.subheader("Summary of Results")
        st.dataframe(df)

        # Show each solution and provide download button
        for fname, sol_str in solutions:
            st.subheader(f"Solution for {fname}")
            st.text(sol_str)
            st.download_button(
                label=f"Download solution for {fname}",
                data=sol_str,
                file_name=f"solution_{fname}",
                mime="text/plain"
            )

        # Cleanup temporary uploaded files
        for path in tmp_paths:
            try:
                os.remove(path)
            except:
                pass

else:
    st.info("Please upload at least one WSP instance file or select preloaded instances to solve.")
