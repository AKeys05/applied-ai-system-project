import datetime

import streamlit as st

from pawpal_system import Pet
from ui_shared import (
    get_breed_options_for_species,
    init_app_state,
    mark_schedule_stale,
    render_sidebar_guidance,
    render_workflow_progress,
    sync_workflow_phase,
)

st.title("🐾 PawPal+")
st.markdown("Welcome to the PawPal+ app - your personal pet care planning assistant!")

with st.expander("Features", expanded=False):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant that helps you manage pet care tasks with:

- 🐾 **Multi-Pet Management**
- ⏰ **Smart Scheduling**
- 🔄 **Recurring Tasks**
- 🎯 **Priority Levels**
- 📅 **Weekly Calendar**
- ⚠️ **Conflict Detection**
- 🔍 **Filtering & Sorting**
- ✅ **Progress Tracking**
"""
    )

owner = init_app_state()
sync_workflow_phase(owner)
render_sidebar_guidance("Home", owner)
render_workflow_progress(owner)

st.divider()
st.subheader("Owner Information")

owner_name = st.text_input("Owner name", value=owner.name, key="home_owner_name")
if owner_name != owner.name:
    owner.name = owner_name

st.caption("Optional: set availability windows to limit when tasks can be scheduled.")

availability_col1, availability_col2, availability_col3 = st.columns(3)
with availability_col1:
    availability_start = st.time_input("Available from", value=datetime.time(8, 0), key="home_availability_start")
with availability_col2:
    availability_end = st.time_input("Available until", value=datetime.time(20, 0), key="home_availability_end")
with availability_col3:
    if st.button("Add Availability Window", key="home_add_availability_window"):
        success, error = owner.add_availability_window(availability_start, availability_end)
        if success:
            mark_schedule_stale()
            st.success("✅ Added availability window")
            st.rerun()
        else:
            st.error(f"❌ {error}")

if owner.availability_windows:
    windows_text = ", ".join(
        f"{start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}"
        for start, end in owner.availability_windows
    )
    st.caption(f"Owner availability: {windows_text}")
    if st.button("Clear Availability Windows", key="home_clear_availability_windows"):
        owner.clear_availability_windows()
        mark_schedule_stale()
        st.success("✅ Cleared owner availability windows")
        st.rerun()

st.divider()
st.subheader("🐾 Manage Pets")

if owner.pets:
    st.write("**Your Pets:**")

    legacy_species_pets = [
        pet.name for pet in owner.pets.values() if pet.species not in {"dog", "cat"}
    ]
    if legacy_species_pets:
        st.warning(
            "Scheduling intelligence is optimized for dog/cat. "
            "Legacy pets currently outside this scope: "
            f"{', '.join(legacy_species_pets)}."
        )

    for pet in list(owner.pets.values()):
        confirm_key = f"_home_confirm_delete_pet_{pet.name}"
        with st.container(border=True):
            info_col, btn_col = st.columns([5, 1])
            with info_col:
                st.markdown(f"**{pet.name}** — {pet.species.capitalize()} / {pet.breed or 'Mixed'}")
                st.caption(
                    f"Activity: {pet.activity_level.capitalize()} • "
                    f"Age: {pet.age_years if pet.age_years is not None else '?'} yrs • "
                    f"{len(pet.tasks)} task(s)"
                )
            with btn_col:
                if st.button("Delete", key=f"home_delete_pet_{pet.name}"):
                    st.session_state[confirm_key] = True
                    st.rerun()

            if st.session_state.get(confirm_key):
                st.warning(f"Delete **{pet.name}** and all their tasks? This cannot be undone.")
                yes_col, no_col, _ = st.columns([1, 1, 4])
                with yes_col:
                    if st.button("Yes, delete", key=f"home_confirm_yes_{pet.name}"):
                        owner.remove_pet(pet.name)
                        st.session_state.pop(confirm_key, None)
                        mark_schedule_stale()
                        st.rerun()
                with no_col:
                    if st.button("Cancel", key=f"home_confirm_no_{pet.name}"):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
else:
    st.info("No pets added yet. Add your first pet below!")

st.markdown("#### Add a Pet")
col1, col2, col3, col4 = st.columns(4)
with col1:
    new_pet_name = st.text_input("Pet name", value="", key="home_new_pet_name")
with col2:
    new_pet_species = st.selectbox("Species", ["dog", "cat"], key="home_new_pet_species")
with col3:
    breed_options = get_breed_options_for_species(new_pet_species)
    new_pet_breed_choice = st.selectbox("Breed", breed_options, key="home_new_pet_breed_choice")
with col4:
    new_pet_activity = st.selectbox(
        "Activity level", ["low", "medium", "high"], index=1, key="home_new_pet_activity"
    )

new_pet_breed = new_pet_breed_choice
if new_pet_breed_choice == "Custom":
    new_pet_breed = (
        st.text_input("Custom breed", value="", key="home_new_pet_breed_custom").strip() or "Mixed"
    )

new_pet_age = st.number_input(
    "Age (years)", min_value=0.0, max_value=40.0, value=2.0, step=0.5, key="home_new_pet_age"
)

if st.button("Add Pet", key="home_add_pet"):
    if owner.get_pet(new_pet_name):
        st.warning(f"⚠️ A pet named '{new_pet_name}' already exists!")
    else:
        new_pet = Pet(
            name=new_pet_name,
            species=new_pet_species,
            breed=new_pet_breed.strip(),
            age_years=float(new_pet_age),
            activity_level=new_pet_activity,
        )
        owner.add_pet(new_pet)
        mark_schedule_stale()
        st.success(f"✅ Added {new_pet_name} the {new_pet_species} ({new_pet_breed})!")
        st.rerun()
