import streamlit as st
from WSP_solver import solve_instance_file

st.title("Workflow Satisfiability Problem (WSP) Solver")

# Upload file
uploaded_file = st.file_uploader("Upload your WSP instance file", type=["txt"])
if uploaded_file:
    # Save uploaded file temporarily
    with open("temp_instance.txt", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    st.write("Solving...")
    # Run solver
    solution_text = solve_instance_file("temp_instance.txt")
    
    st.success("Solution generated!")
    
    # Display solution in web page
    st.text(solution_text)
    
    # Allow download
    st.download_button(
        label="Download Solution",
        data=solution_text,
        file_name=f"solution_{uploaded_file.name}",
        mime="text/plain"
    )
