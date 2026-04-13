import datetime

import streamlit as st

from pawpal_system import Pet
from ui_shared import (
    get_breed_options_for_species,
    init_app_state,
    render_workflow_progress,
    sync_workflow_phase,
)

st.title("🐾 PawPal+")
st.markdown("Welcome to the PawPal+ app - your personal pet care planning assistant!")

with st.expander("Features", expanded=True):
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
render_workflow_progress(owner)

st.divider()
st.subheader("Owner Information")

owner_name = st.text_input("Owner name", value=owner.name, key="home_owner_name")
if owner_name != owner.name:
    owner.name = owner_name

owner_col1, owner_col2 = st.columns(2)
with owner_col1:
    owner_timezone = st.text_input("Timezone", value=owner.timezone, key="home_owner_timezone")
    if owner_timezone != owner.timezone:
        owner.set_timezone(owner_timezone)
with owner_col2:
    st.caption("Optional availability windows guide when scheduling can happen.")

availability_col1, availability_col2, availability_col3 = st.columns(3)
with availability_col1:
    availability_start = st.time_input("Available from", value=datetime.time(8, 0), key="home_availability_start")
with availability_col2:
    availability_end = st.time_input("Available until", value=datetime.time(20, 0), key="home_availability_end")
with availability_col3:
    if st.button("Add Availability Window", key="home_add_availability_window"):
        success, error = owner.add_availability_window(availability_start, availability_end)
        if success:
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
        st.success("✅ Cleared owner availability windows")
        st.rerun()

st.divider()
st.subheader("🐾 Manage Pets")

if owner.pets:
    st.write("**Your Pets:**")
    pets_data = []
    for pet in owner.pets.values():
        pets_data.append(
            {
                "Name": pet.name,
                "Species": pet.species.capitalize(),
                "Breed": pet.breed or "-",
                "Activity": pet.activity_level.capitalize() if pet.activity_level else "-",
                "Tasks": len(pet.tasks),
            }
        )
    st.table(pets_data)
else:
    st.info("No pets added yet. Add your first pet below!")

st.markdown("#### Add a Pet")
col1, col2, col3, col4 = st.columns(4)
with col1:
    new_pet_name = st.text_input("Pet name", value="Mochi", key="home_new_pet_name")
with col2:
    new_pet_species = st.selectbox(
        "Species", ["dog", "cat", "bird", "rabbit", "other"], key="home_new_pet_species"
    )
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
        st.success(f"✅ Added {new_pet_name} the {new_pet_species} ({new_pet_breed})!")
        st.rerun()
