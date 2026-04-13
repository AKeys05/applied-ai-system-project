import streamlit as st
import datetime
from pawpal_system import Owner, Pet, Task, Priority, Scheduler, Frequency, ScheduleConstraint

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ app - your personal pet care planning assistant!"""
)

with st.expander("Features", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant that helps you manage pet care tasks with:

- 🐾 **Multi-Pet Management** - Track tasks for multiple pets (dogs, cats, birds, and more)
- ⏰ **Smart Scheduling** - Set preferred times and time constraints for tasks
- 🔄 **Recurring Tasks** - Daily, weekly, biweekly, or monthly recurring tasks
- 🎯 **Priority Levels** - Organize tasks by High, Medium, or Low priority
- 📅 **Weekly Calendar** - Visualize your entire week's schedule at a glance
- ⚠️ **Conflict Detection** - Automatic detection and resolution of scheduling conflicts
- 🔍 **Filtering & Sorting** - Filter by pet, completion status, or sort by time/priority
- ✅ **Progress Tracking** - Mark tasks complete and track recurring task chains
"""
    )


st.divider()

# Initialize owner in session_state
st.subheader("Owner Information")
owner_name = st.text_input("Owner name", value="Jordan")

if "owner" not in st.session_state:
    st.session_state.owner = Owner(owner_name)
else:
    # Update owner name if changed
    if st.session_state.owner.name != owner_name:
        st.session_state.owner.name = owner_name

owner = st.session_state.owner

# Backward compatibility for sessions created before profile fields existed
if not hasattr(owner, "timezone"):
    owner.timezone = "Local"
if not hasattr(owner, "availability_windows"):
    owner.availability_windows = []

owner_col1, owner_col2 = st.columns(2)
with owner_col1:
    owner_timezone = st.text_input("Timezone", value=owner.timezone, key="owner_timezone")
    if owner_timezone != owner.timezone:
        owner.set_timezone(owner_timezone)
with owner_col2:
    st.caption("Optional availability windows guide when scheduling can happen.")

availability_col1, availability_col2, availability_col3 = st.columns(3)
with availability_col1:
    availability_start = st.time_input("Available from", value=datetime.time(8, 0), key="availability_start")
with availability_col2:
    availability_end = st.time_input("Available until", value=datetime.time(20, 0), key="availability_end")
with availability_col3:
    if st.button("Add Availability Window"):
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
    if st.button("Clear Availability Windows"):
        owner.clear_availability_windows()
        st.success("✅ Cleared owner availability windows")
        st.rerun()

# Helper function for displaying task cards
def display_task_card(schedule_item: dict, compact: bool = False, key_suffix: str = ""):
	"""Display task with priority indicators and time context.

	Args:
		schedule_item: Dict with keys 'task', 'time', 'pet_name', 'reason'
		compact: If True, use compact layout for calendar grid
		key_suffix: Unique suffix for button keys
	"""
	task = schedule_item['task']
	scheduled_time = schedule_item['time']

	# Priority color coding
	priority_colors = {
		Priority.HIGH: "🔴",
		Priority.MEDIUM: "🟡",
		Priority.LOW: "🟢"
	}

	if compact:
		# Compact view for weekly calendar
		if scheduled_time:
			st.markdown(f"{priority_colors[task.priority]} **{scheduled_time.strftime('%I:%M %p')}**")
			st.caption(f"{task.title} ({task.duration}m)")
			st.caption(f"🐾 {task.pet_name}")
		else:
			st.caption(f"⚠️ {task.title} (unscheduled)")
	else:
		# Full view for daily schedule
		st.markdown(f"{priority_colors[task.priority]} **{task.title}**")
		time_str = scheduled_time.strftime('%I:%M %p') if scheduled_time else "Not scheduled"
		st.caption(f"{time_str} • {task.duration} min • {task.pet_name}")

st.divider()

# Pet Management Section
st.subheader("🐾 Manage Pets")

# Display existing pets
if owner.pets:
    st.write("**Your Pets:**")
    pets_data = []
    for pet in owner.pets.values():
        pets_data.append({
            "Name": pet.name,
            "Species": pet.species.capitalize(),
            "Breed": pet.breed or "-",
            "Activity": pet.activity_level.capitalize() if pet.activity_level else "-",
            "Tasks": len(pet.tasks)
        })
    st.table(pets_data)
else:
    st.info("No pets added yet. Add your first pet below!")

# Add new pet
st.markdown("#### Add a Pet")
col1, col2, col3, col4 = st.columns(4)
with col1:
    new_pet_name = st.text_input("Pet name", value="Mochi", key="new_pet_name")
with col2:
    new_pet_species = st.selectbox("Species", ["dog", "cat", "bird", "rabbit", "other"], key="new_pet_species")
with col3:
    new_pet_breed = st.text_input("Breed", value="Mixed", key="new_pet_breed")
with col4:
    new_pet_activity = st.selectbox("Activity level", ["low", "medium", "high"], index=1, key="new_pet_activity")

new_pet_age = st.number_input("Age (years)", min_value=0.0, max_value=40.0, value=2.0, step=0.5, key="new_pet_age")

if st.button("Add Pet"):
    # Check if pet already exists
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

st.divider()

st.markdown("### Tasks")
st.caption("Add tasks for your pets.")

if not owner.pets:
    st.warning("⚠️ Please add at least one pet before creating tasks.")
else:
    # Pet selector for tasks
    pet_names = [pet.name for pet in owner.pets.values()]
    selected_pet_name = st.selectbox("Select pet for task", pet_names)

    col1, col2, col3 = st.columns(3)
    with col1:
        task_title = st.text_input("Task title", value="Morning walk")
    with col2:
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
    with col3:
        priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

    # Optional preferred time
    use_preferred_time = st.checkbox("Set preferred time")
    preferred_time = None
    if use_preferred_time:
        preferred_time = st.time_input("Preferred time", value=datetime.time(8, 0))

    # Optional time constraint
    add_constraint = st.checkbox("Add time constraint")
    time_constraint = None
    schedule_constraint = ScheduleConstraint()
    if add_constraint:
        constraint_type = st.radio("Constraint type", ["before", "after"])
        constraint_time = st.time_input("Constraint time", value=None)
        constraint_strength = st.selectbox("Constraint strength", ["Hard", "Soft"], index=0)
        if constraint_time:
            time_constraint = f"{constraint_type} {constraint_time.strftime('%H:%M')}"
            if constraint_type == "before":
                schedule_constraint.latest_end = constraint_time
            else:
                schedule_constraint.earliest_start = constraint_time
            schedule_constraint.hard_constraint = constraint_strength == "Hard"
            schedule_constraint.source = "user"

    # Recurring task options
    is_recurring = st.checkbox("Make this a recurring task")
    frequency = None
    scheduled_date = None

    if is_recurring:
        col1, col2 = st.columns(2)
        with col1:
            frequency_str = st.selectbox(
                "Frequency",
                ["daily", "weekly", "biweekly", "monthly"],
                help="How often should this task repeat?"
            )
            frequency = Frequency(frequency_str)
        with col2:
            scheduled_date = st.date_input(
                "Start date",
                value=datetime.date.today(),
                help="When should this recurring task start?"
            )
    else:
        # For non-recurring tasks, set scheduled_date to today
        scheduled_date = datetime.date.today()

    if st.button("Add task"):
        # Map string priority to Priority enum
        priority_map = {
            "low": Priority.LOW,
            "medium": Priority.MEDIUM,
            "high": Priority.HIGH
        }

        task = Task(
            title=task_title,
            duration=int(duration),
            priority=priority_map[priority],
            pet_name=selected_pet_name,
            preferred_time=preferred_time,
            time_constraint=time_constraint,
            schedule_constraint=schedule_constraint,
            frequency=frequency,
            scheduled_date=scheduled_date
        )

        # Guardrails for invalid task settings
        is_valid, error = task.validate_basic_fields()
        if not is_valid:
            st.error(f"❌ {error}")
            st.stop()

        is_valid, error = task.validate_time_settings()
        if not is_valid:
            st.error(f"❌ {error}")
            st.stop()

        # Add task using owner API (includes validation + indexing)
        if owner.add_task(selected_pet_name, task):
            recurring_msg = f" (recurring {frequency.value})" if frequency else ""
            st.success(f"✅ Added task '{task_title}' for {selected_pet_name}{recurring_msg}!")
            st.rerun()
        else:
            st.error("❌ Could not add task. Check pet selection and constraint settings.")

    # Display all tasks with enhanced filtering and sorting
    st.markdown("#### Current Tasks")

    # Filter and sort controls
    col1, col2, col3 = st.columns(3)

    with col1:
        # Pet filter
        pet_options = ["All Pets"] + list(owner.pets.keys())
        selected_pet_filter = st.selectbox("Filter by pet", pet_options, key="task_pet_filter")

    with col2:
        # Sort option
        sort_option = st.selectbox(
            "Sort by",
            ["Time", "Priority (High to Low)", "Pet Name"],
            key="task_sort"
        )

    with col3:
        # Completion filter
        show_completed = st.checkbox("Show completed tasks inline", value=False)

    st.divider()

    # Get and filter tasks
    all_tasks = owner.get_all_tasks()

    # Apply pet filter
    if selected_pet_filter != "All Pets":
        all_tasks = Task.filter_by_pet(all_tasks, selected_pet_filter)

    # Apply completion filter
    if not show_completed:
        all_tasks = Task.filter_by_completion(all_tasks, completed=False)

    # Apply sorting
    if sort_option == "Time":
        all_tasks = Task.sort_by_time(all_tasks)
    elif sort_option == "Priority (High to Low)":
        all_tasks = sorted(all_tasks, key=lambda t: t.priority.value, reverse=True)
    elif sort_option == "Pet Name":
        all_tasks = sorted(all_tasks, key=lambda t: t.pet_name)

    # Display tasks
    if not all_tasks:
        st.info("No tasks match your filters.")
    else:
        for task in all_tasks:
            # Priority color indicators
            priority_colors = {
                Priority.HIGH: "🔴",
                Priority.MEDIUM: "🟡",
                Priority.LOW: "🟢"
            }

            col1, col2 = st.columns([4, 1])

            with col1:
                # Task title with status and priority
                recurring_badge = f" `{task.frequency.value}`" if task.frequency else ""
                status_icon = "✅" if task.completed else "⭕"

                st.markdown(f"{status_icon} {priority_colors[task.priority]} **{task.title}**{recurring_badge}")

                # Enhanced details with time context
                details_parts = [
                    f"{task.duration} min",
                    f"{task.priority.name} priority",
                    f"🐾 {task.pet_name}"
                ]

                # Add time context
                if task.preferred_time:
                    details_parts.append(f"⏰ Prefers {task.preferred_time.strftime('%I:%M %p')}")

                # Add date context
                if task.scheduled_date:
                    today = datetime.date.today()
                    if task.scheduled_date == today:
                        details_parts.append("📅 Today")
                    elif task.scheduled_date < today:
                        days_ago = (today - task.scheduled_date).days
                        details_parts.append(f"📅 {days_ago} day{'s' if days_ago > 1 else ''} overdue")
                    else:
                        details_parts.append(f"📅 {task.scheduled_date.strftime('%b %d')}")

                st.caption(" • ".join(details_parts))

                # Duration visualization
                max_duration = 120  # 2 hours for scaling
                duration_pct = min(task.duration / max_duration, 1.0)
                st.progress(duration_pct, text=f"{task.duration} minutes")

            with col2:
                # Complete button (only for incomplete tasks)
                if not task.completed:
                    if st.button("✓ Complete", key=f"complete_{task.id}"):
                        success, next_task = owner.complete_task(task.id)

                        if success:
                            if next_task:
                                st.success(f"✅ Completed! Next: {next_task.scheduled_date}")
                            else:
                                st.success("✅ Task completed!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to complete task")

            st.divider()

    # Completed tasks in collapsible section
    if not show_completed:  # Only show expander if not showing inline
        completed_tasks = [t for t in owner.get_all_tasks() if t.completed]
        if completed_tasks:
            with st.expander(f"📋 Completed Tasks ({len(completed_tasks)})"):
                tasks_data = []
                for task in completed_tasks:
                    tasks_data.append({
                        "Pet": task.pet_name,
                        "Task": task.title,
                        "Priority": task.priority.name,
                        "Date": task.scheduled_date.strftime('%Y-%m-%d') if task.scheduled_date else "-"
                    })
                st.table(tasks_data)

st.divider()

st.subheader("📅 Schedule View")

tab1, tab2 = st.tabs(["📋 Daily Schedule", "📅 Weekly Calendar"])

# TAB 1: Daily Schedule (existing functionality)
with tab1:
    if st.button("Generate Daily Schedule"):
        # Check if there are any tasks
        all_tasks = owner.get_all_tasks()

        if not all_tasks:
            st.warning("⚠️ Please add at least one task before generating a schedule.")
        else:
            # Create scheduler and check for preferred time conflicts BEFORE scheduling
            scheduler = Scheduler(owner)

            # Check for potential conflicts in preferred times
            warnings = scheduler.detect_preferred_time_conflicts()
            if warnings:
                st.warning("⚠️ Preferred Time Conflicts Detected:")
                for warning in warnings:
                    if "Same pet conflict" in warning:
                        st.error(warning)
                    else:
                        st.info(warning)
                st.caption("The scheduler will try to resolve these conflicts automatically.")

            # Generate schedule
            schedule = scheduler.generate_schedule()

            # Display the schedule explanation
            st.success("✅ Schedule generated!")
            st.markdown("### Today's Schedule")
            st.text(scheduler.explain_schedule())

            # Show metadata that supports reliability and future RAG integration
            with st.expander("Decision Metadata"):
                for item in schedule:
                    task = item['task']
                    confidence = item.get('confidence_score', 0.0)
                    rules = item.get('applied_rules', [])
                    sources = item.get('retrieval_sources', [])
                    source_text = ", ".join(sources) if sources else "-"
                    st.caption(
                        f"{task.title}: confidence={confidence:.2f} | "
                        f"rules={', '.join(rules) if rules else '-'} | "
                        f"sources={source_text}"
                    )

            reliability = scheduler.get_reliability_report()
            with st.expander("Reliability Summary", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Overall Confidence", f"{reliability['overall_confidence']:.2f}")
                with col2:
                    st.metric("Scheduled", reliability['scheduled_tasks'])
                with col3:
                    st.metric("Unscheduled", len(reliability['unscheduled_tasks']))

                if reliability['guardrail_warnings']:
                    st.warning("Guardrail warnings:")
                    for warning in reliability['guardrail_warnings']:
                        st.caption(f"- {warning}")

            # Check for conflicts in final schedule (should be rare)
            conflicts = scheduler.detect_conflicts()
            if conflicts:
                st.error("⚠️ Final schedule conflicts detected:")
                for conflict in conflicts:
                    st.write(f"- {conflict}")
            else:
                st.success("✓ No scheduling conflicts in final schedule!")

# TAB 2: Weekly Calendar (NEW)
with tab2:
    st.markdown("### Weekly Calendar View")

    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        scheduler_helper = Scheduler(owner)
        monday, sunday = scheduler_helper.get_week_date_range()
        start_date = st.date_input("Week starting (Monday)", value=monday)
    with col2:
        from datetime import timedelta
        end_date = start_date + timedelta(days=6)
        st.info(f"Showing: {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}")

    if st.button("Generate Weekly Calendar"):
        scheduler = Scheduler(owner)

        # Generate schedules for 7 days
        weekly_data = {}
        for i in range(7):
            current_day = start_date + timedelta(days=i)
            schedule = scheduler.generate_schedule(target_date=current_day)
            weekly_data[current_day] = schedule

        st.markdown("---")

        # Display calendar header
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        cols = st.columns(7)

        for idx, col in enumerate(cols):
            with col:
                day = start_date + timedelta(days=idx)
                st.markdown(f"**{day_names[idx]}**")
                st.caption(day.strftime("%b %d"))

        # Display tasks in grid
        cols = st.columns(7)

        for idx, col in enumerate(cols):
            day = start_date + timedelta(days=idx)
            schedule = weekly_data[day]

            with col:
                if not schedule:
                    st.caption("_No tasks_")
                else:
                    # Show only scheduled tasks
                    scheduled_tasks = [item for item in schedule if item['time'] is not None]

                    if not scheduled_tasks:
                        st.caption("_No tasks_")
                    else:
                        for item in scheduled_tasks:
                            display_task_card(item, compact=True, key_suffix=day.isoformat())
                            st.divider()

        # Summary statistics
        st.markdown("---")
        st.markdown("### Weekly Summary")

        total_tasks = sum(len(schedule) for schedule in weekly_data.values())
        total_scheduled = sum(
            sum(1 for item in schedule if item['time'] is not None)
            for schedule in weekly_data.values()
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Tasks", total_tasks)
        with col2:
            st.metric("Scheduled", total_scheduled)
        with col3:
            st.metric("Unscheduled", total_tasks - total_scheduled)
