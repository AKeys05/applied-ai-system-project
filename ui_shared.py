import datetime
import json
from pathlib import Path

import streamlit as st

from pawpal_system import Owner, Priority


def init_app_state() -> Owner:
    if "workflow_phase" not in st.session_state:
        st.session_state.workflow_phase = "owner_setup"
    if "auto_generate_daily_schedule" not in st.session_state:
        st.session_state.auto_generate_daily_schedule = False
    if "last_routine_profiles" not in st.session_state:
        st.session_state.last_routine_profiles = {}
    if "schedule_handoff_summary" not in st.session_state:
        st.session_state.schedule_handoff_summary = None
    if "owner" not in st.session_state:
        st.session_state.owner = Owner("Jordan")

    owner = st.session_state.owner
    if not hasattr(owner, "timezone"):
        owner.timezone = "Local"
    if not hasattr(owner, "availability_windows"):
        owner.availability_windows = []
    return owner


def owner_profile_complete(owner_obj: Owner) -> bool:
    return bool(owner_obj.name.strip()) and bool(owner_obj.timezone.strip())


def pet_profile_complete(owner_obj: Owner) -> bool:
    return len(owner_obj.pets) > 0


def routine_ready(owner_obj: Owner) -> bool:
    return owner_profile_complete(owner_obj) and pet_profile_complete(owner_obj)


def sync_workflow_phase(owner_obj: Owner) -> None:
    owner_ready = owner_profile_complete(owner_obj)
    pets_ready = pet_profile_complete(owner_obj)

    if st.session_state.workflow_phase == "owner_setup" and owner_ready:
        st.session_state.workflow_phase = "pet_setup"
    if st.session_state.workflow_phase == "pet_setup" and pets_ready:
        st.session_state.workflow_phase = "routine_setup"


def render_workflow_progress(owner_obj: Owner) -> tuple[bool, bool, bool]:
    owner_ready = owner_profile_complete(owner_obj)
    pets_ready = pet_profile_complete(owner_obj)
    ready = owner_ready and pets_ready

    st.markdown("### Workflow Progress")
    status_col1, status_col2, status_col3 = st.columns(3)
    with status_col1:
        st.metric("Owner Profile", "Complete" if owner_ready else "Needed")
    with status_col2:
        st.metric("Pet Profiles", "Complete" if pets_ready else "Needed")
    with status_col3:
        current_phase_label = st.session_state.workflow_phase.replace("_", " ").title()
        st.metric("Current Phase", current_phase_label)

    if not owner_ready:
        st.info("Start with owner details: name and timezone.")
    elif not pets_ready:
        st.info("Add at least one pet to unlock routine generation.")
    else:
        st.success("Profile setup complete. Build a routine and continue to scheduling.")

    return owner_ready, pets_ready, ready


def get_breed_options_for_species(species: str) -> list[str]:
    try:
        data_path = Path(__file__).resolve().parent / "data" / "breed_guidelines.json"
        with open(data_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        breeds = []
        for breed_name, info in data.get("breeds", {}).items():
            if info.get("species") == species:
                breeds.append(breed_name.title())
        breeds = sorted(set(breeds))
        return breeds + ["Mixed", "Custom"] if breeds else ["Mixed", "Custom"]
    except Exception:
        return ["Mixed", "Custom"]


def display_task_card(schedule_item: dict, compact: bool = False) -> None:
    task = schedule_item["task"]
    scheduled_time = schedule_item["time"]

    priority_colors = {
        Priority.HIGH: "🔴",
        Priority.MEDIUM: "🟡",
        Priority.LOW: "🟢",
    }

    if compact:
        if scheduled_time:
            st.markdown(f"{priority_colors[task.priority]} **{scheduled_time.strftime('%I:%M %p')}**")
            st.caption(f"{task.title} ({task.duration}m)")
            st.caption(f"🐾 {task.pet_name}")
        else:
            st.caption(f"⚠️ {task.title} (unscheduled)")
    else:
        st.markdown(f"{priority_colors[task.priority]} **{task.title}**")
        time_str = scheduled_time.strftime("%I:%M %p") if scheduled_time else "Not scheduled"
        st.caption(f"{time_str} • {task.duration} min • {task.pet_name}")


def default_time(hour: int, minute: int = 0) -> datetime.time:
    return datetime.time(hour, minute)
