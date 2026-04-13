import streamlit as st

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

pg = st.navigation(
    [
        st.Page("pages/home.py", title="Home", icon=":material/home:", default=True),
        st.Page("pages/task_builder.py", title="Task Builder", icon=":material/edit_note:"),
        st.Page("pages/schedule.py", title="Schedule", icon=":material/calendar_month:"),
    ]
)
pg.run()
