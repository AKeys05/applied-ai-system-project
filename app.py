import os
import streamlit as st

if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

st.set_page_config(page_title="PetPlanify", page_icon="🐾", layout="centered")

pg = st.navigation(
    [
        st.Page("pages/home.py", title="Home", icon=":material/home:", default=True),
        st.Page("pages/task_builder.py", title="Task Builder", icon=":material/edit_note:"),
        st.Page("pages/schedule.py", title="Schedule", icon=":material/calendar_month:"),
    ]
)
pg.run()
