import datetime

import streamlit as st

from pawpal_system import Frequency, Priority, RoutineProfile, ScheduleConstraint, Task
from ui_shared import (
    init_app_state,
    render_sidebar_guidance,
    render_workflow_progress,
    routine_ready,
    sync_workflow_phase,
)

st.title("🧭 Task & Routine Builder")
owner = init_app_state()
sync_workflow_phase(owner)
render_sidebar_guidance("Task Builder", owner)
render_workflow_progress(owner)

st.markdown("### Tasks")
st.caption("Use Routine Builder to auto-create a daily routine. Manual task entry is available under Advanced.")

if not routine_ready(owner):
    st.warning("⚠️ Complete owner profile and add at least one pet on Home before creating tasks.")
    st.stop()

st.markdown("#### 🧭 Routine Builder")
routine_pet_name = st.selectbox("Select pet for routine", [pet.name for pet in owner.pets.values()], key="task_routine_pet_select")
profile_defaults = st.session_state.last_routine_profiles.get(routine_pet_name, {})

copy_candidates = [
    pet_name for pet_name in st.session_state.last_routine_profiles.keys() if pet_name != routine_pet_name
]
if copy_candidates:
    copy_col1, copy_col2 = st.columns([3, 1])
    with copy_col1:
        copy_from_pet = st.selectbox(
            "Copy routine settings from",
            copy_candidates,
            key=f"task_copy_from_pet_{routine_pet_name}",
        )
    with copy_col2:
        if st.button("Copy", key=f"task_copy_profile_{routine_pet_name}"):
            st.session_state.last_routine_profiles[routine_pet_name] = dict(
                st.session_state.last_routine_profiles.get(copy_from_pet, {})
            )
            st.success(f"Copied routine settings from {copy_from_pet}.")
            st.rerun()


def _time_default(field: str, fallback: datetime.time) -> datetime.time:
    return profile_defaults.get(field, fallback)


with st.form("task_routine_builder_form"):
    st.caption("Set daily care preferences. PawPal+ will auto-generate tasks from this profile.")

    col1, col2, col3 = st.columns(3)
    with col1:
        walks_per_day = st.number_input(
            "Walks per day",
            min_value=0,
            max_value=6,
            value=int(profile_defaults.get("walks_per_day", 1)),
            step=1,
            key=f"task_walks_per_day_{routine_pet_name}",
        )
        meals_per_day = st.number_input(
            "Meals per day",
            min_value=0,
            max_value=6,
            value=int(profile_defaults.get("meals_per_day", 2)),
            step=1,
            key=f"task_meals_per_day_{routine_pet_name}",
        )
    with col2:
        play_sessions = st.number_input(
            "Play/enrichment sessions",
            min_value=0,
            max_value=6,
            value=int(profile_defaults.get("play_sessions_per_day", 1)),
            step=1,
            key=f"task_play_sessions_{routine_pet_name}",
        )
        grooming_per_week = st.number_input(
            "Grooming sessions/week",
            min_value=0,
            max_value=7,
            value=int(profile_defaults.get("grooming_sessions_per_week", 0)),
            step=1,
            key=f"task_grooming_per_week_{routine_pet_name}",
        )
    with col3:
        med_doses = st.number_input(
            "Medication doses/day",
            min_value=0,
            max_value=6,
            value=int(profile_defaults.get("med_doses", 0)),
            step=1,
            key=f"task_med_doses_{routine_pet_name}",
        )

    st.markdown("**Preferred windows**")
    w1, w2 = st.columns(2)
    with w1:
        walk_window_start = st.time_input(
            "Walk window start",
            value=_time_default("walk_window_start", datetime.time(7, 0)),
            key=f"task_walk_window_start_{routine_pet_name}",
        )
        meal_window_start = st.time_input(
            "Meal window start",
            value=_time_default("meal_window_start", datetime.time(7, 0)),
            key=f"task_meal_window_start_{routine_pet_name}",
        )
        play_window_start = st.time_input(
            "Play window start",
            value=_time_default("play_window_start", datetime.time(8, 0)),
            key=f"task_play_window_start_{routine_pet_name}",
        )
    with w2:
        walk_window_end = st.time_input(
            "Walk window end",
            value=_time_default("walk_window_end", datetime.time(10, 0)),
            key=f"task_walk_window_end_{routine_pet_name}",
        )
        meal_window_end = st.time_input(
            "Meal window end",
            value=_time_default("meal_window_end", datetime.time(19, 0)),
            key=f"task_meal_window_end_{routine_pet_name}",
        )
        play_window_end = st.time_input(
            "Play window end",
            value=_time_default("play_window_end", datetime.time(20, 0)),
            key=f"task_play_window_end_{routine_pet_name}",
        )

    medication_times = []
    default_med_times = profile_defaults.get("medication_times", [])
    if med_doses > 0:
        st.markdown("**Medication times**")
        for idx in range(int(med_doses)):
            default_med_time = datetime.time(8 + idx, 0)
            if idx < len(default_med_times):
                default_med_time = default_med_times[idx]
            medication_times.append(
                st.time_input(
                    f"Medication time #{idx + 1}",
                    value=default_med_time,
                    key=f"task_med_time_{routine_pet_name}_{idx}",
                )
            )

    regenerate_mode = st.checkbox(
        "Replace previously generated profile tasks for this pet",
        value=bool(profile_defaults.get("regenerate_mode", True)),
        key=f"task_regenerate_mode_{routine_pet_name}",
    )
    submitted = st.form_submit_button("Generate Routine Tasks")

    if submitted:
        st.session_state.last_routine_profiles[routine_pet_name] = {
            "walks_per_day": int(walks_per_day),
            "meals_per_day": int(meals_per_day),
            "play_sessions_per_day": int(play_sessions),
            "grooming_sessions_per_week": int(grooming_per_week),
            "med_doses": int(med_doses),
            "medication_times": list(medication_times),
            "walk_window_start": walk_window_start,
            "walk_window_end": walk_window_end,
            "meal_window_start": meal_window_start,
            "meal_window_end": meal_window_end,
            "play_window_start": play_window_start,
            "play_window_end": play_window_end,
            "regenerate_mode": bool(regenerate_mode),
        }

        profile = RoutineProfile(
            walks_per_day=int(walks_per_day),
            meals_per_day=int(meals_per_day),
            play_sessions_per_day=int(play_sessions),
            medication_times=medication_times,
            grooming_sessions_per_week=int(grooming_per_week),
            walk_window_start=walk_window_start,
            walk_window_end=walk_window_end,
            meal_window_start=meal_window_start,
            meal_window_end=meal_window_end,
            play_window_start=play_window_start,
            play_window_end=play_window_end,
        )
        success, tasks_created, error = owner.generate_tasks_from_profile(
            routine_pet_name,
            profile,
            replace_existing=regenerate_mode,
        )
        if success:
            st.success(f"✅ Generated {tasks_created} tasks for {routine_pet_name}.")
            st.session_state.workflow_phase = "review"
            st.rerun()
        else:
            st.error(f"❌ Could not generate routine tasks: {error}")

summary = getattr(owner, "last_generation_summary", {})
if summary and summary.get("pet_name") == routine_pet_name:
    st.markdown("**Last Generation Summary**")
    s1, s2 = st.columns(2)
    with s1:
        st.metric("Created", summary.get("created_count", 0))
    with s2:
        st.metric("Removed", summary.get("removed_count", 0))

generated_tasks = [
    t for t in owner.get_tasks_for_pet(routine_pet_name) if t.task_source == "profile_generated"
]
if generated_tasks:
    st.markdown("#### Review Generated Tasks")
    st.caption("Adjust generated tasks before schedule generation. You can skip, set preferred time, and lock time.")
    for task in generated_tasks:
        c1, c2, c3 = st.columns([3, 1, 2])
        with c1:
            status = "⏭️ Skipped" if task.skipped else "✅ Included"
            lock_status = "🔒 Locked" if task.locked_preferred_time else "🔓 Flexible"
            preferred_label = task.preferred_time.strftime("%I:%M %p") if task.preferred_time else "-"
            st.caption(f"{task.title} | {status} | {lock_status} | preferred: {preferred_label}")
        with c2:
            if task.skipped:
                if st.button("Unskip", key=f"task_unskip_{task.id}"):
                    owner.edit_task(task.id, skipped=False)
                    st.rerun()
            else:
                if st.button("Skip", key=f"task_skip_{task.id}"):
                    owner.edit_task(task.id, skipped=True)
                    st.rerun()
        with c3:
            lock_time = st.time_input(
                "Preferred",
                value=task.preferred_time or datetime.time(8, 0),
                key=f"task_lock_time_{task.id}",
            )
            if task.locked_preferred_time:
                if st.button("Unlock", key=f"task_unlock_{task.id}"):
                    owner.edit_task(task.id, locked_preferred_time=False)
                    st.rerun()
            else:
                if st.button("Set + Lock", key=f"task_lock_{task.id}"):
                    owner.edit_task(task.id, preferred_time=lock_time, locked_preferred_time=True)
                    st.rerun()

    if st.button("Continue to Schedule", key="task_continue_to_schedule"):
        included_count = len([task for task in generated_tasks if not task.skipped])
        skipped_count = len([task for task in generated_tasks if task.skipped])
        locked_count = len([task for task in generated_tasks if task.locked_preferred_time])
        st.session_state.schedule_handoff_summary = {
            "pet_name": routine_pet_name,
            "included": included_count,
            "skipped": skipped_count,
            "locked": locked_count,
        }
        st.session_state.workflow_phase = "scheduling"
        st.session_state.auto_generate_daily_schedule = True
        st.switch_page("pages/schedule.py")

st.divider()
with st.expander("➕ Advanced: Manual Task Entry", expanded=False):
    pet_names = [pet.name for pet in owner.pets.values()]
    selected_pet_name = st.selectbox("Select pet for task", pet_names, key="task_selected_pet_name")

    col1, col2, col3 = st.columns(3)
    with col1:
        task_title = st.text_input("Task title", value="Morning walk", key="task_title")
    with col2:
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20, key="task_duration")
    with col3:
        priority = st.selectbox("Priority", ["low", "medium", "high"], index=2, key="task_priority")

    use_preferred_time = st.checkbox("Set preferred time", key="task_use_preferred_time")
    preferred_time = None
    if use_preferred_time:
        preferred_time = st.time_input("Preferred time", value=datetime.time(8, 0), key="task_preferred_time")

    add_constraint = st.checkbox("Add time constraint", key="task_add_constraint")
    time_constraint = None
    schedule_constraint = ScheduleConstraint()
    if add_constraint:
        constraint_type = st.radio("Constraint type", ["before", "after"], key="task_constraint_type")
        constraint_time = st.time_input("Constraint time", value=None, key="task_constraint_time")
        constraint_strength = st.selectbox("Constraint strength", ["Hard", "Soft"], index=0, key="task_constraint_strength")
        if constraint_time:
            time_constraint = f"{constraint_type} {constraint_time.strftime('%H:%M')}"
            if constraint_type == "before":
                schedule_constraint.latest_end = constraint_time
            else:
                schedule_constraint.earliest_start = constraint_time
            schedule_constraint.hard_constraint = constraint_strength == "Hard"
            schedule_constraint.source = "user"

    is_recurring = st.checkbox("Make this a recurring task", key="task_is_recurring")
    frequency = None
    if is_recurring:
        col1, col2 = st.columns(2)
        with col1:
            frequency_str = st.selectbox(
                "Frequency",
                ["daily", "weekly", "biweekly", "monthly"],
                key="task_frequency",
            )
            frequency = Frequency(frequency_str)
        with col2:
            scheduled_date = st.date_input("Start date", value=datetime.date.today(), key="task_scheduled_date")
    else:
        scheduled_date = datetime.date.today()

    if st.button("Add task", key="task_add_button"):
        priority_map = {"low": Priority.LOW, "medium": Priority.MEDIUM, "high": Priority.HIGH}
        task = Task(
            title=task_title,
            duration=int(duration),
            priority=priority_map[priority],
            pet_name=selected_pet_name,
            preferred_time=preferred_time,
            time_constraint=time_constraint,
            schedule_constraint=schedule_constraint,
            frequency=frequency,
            scheduled_date=scheduled_date,
        )

        is_valid, error = task.validate_basic_fields()
        if not is_valid:
            st.error(f"❌ {error}")
            st.stop()

        is_valid, error = task.validate_time_settings()
        if not is_valid:
            st.error(f"❌ {error}")
            st.stop()

        if owner.add_task(selected_pet_name, task):
            recurring_msg = f" (recurring {frequency.value})" if frequency else ""
            st.success(f"✅ Added task '{task_title}' for {selected_pet_name}{recurring_msg}!")
            st.rerun()
        else:
            st.error("❌ Could not add task. Check pet selection and constraint settings.")

st.markdown("#### Current Tasks")
col1, col2, col3 = st.columns(3)
with col1:
    pet_options = ["All Pets"] + list(owner.pets.keys())
    selected_pet_filter = st.selectbox("Filter by pet", pet_options, key="task_pet_filter")
with col2:
    sort_option = st.selectbox("Sort by", ["Time", "Priority (High to Low)", "Pet Name"], key="task_sort")
with col3:
    show_completed = st.checkbox("Show completed tasks inline", value=False, key="task_show_completed")

st.divider()
all_tasks = owner.get_all_tasks()
if selected_pet_filter != "All Pets":
    all_tasks = Task.filter_by_pet(all_tasks, selected_pet_filter)
if not show_completed:
    all_tasks = Task.filter_by_completion(all_tasks, completed=False)

if sort_option == "Time":
    all_tasks = Task.sort_by_time(all_tasks)
elif sort_option == "Priority (High to Low)":
    all_tasks = sorted(all_tasks, key=lambda t: t.priority.value, reverse=True)
else:
    all_tasks = sorted(all_tasks, key=lambda t: t.pet_name)

if not all_tasks:
    st.info("No tasks match your filters.")
else:
    priority_colors = {Priority.HIGH: "🔴", Priority.MEDIUM: "🟡", Priority.LOW: "🟢"}
    for task in all_tasks:
        col1, col2 = st.columns([4, 1])
        with col1:
            recurring_badge = f" `{task.frequency.value}`" if task.frequency else ""
            status_icon = "✅" if task.completed else "⭕"
            source_badges = ["🎯 Profile" if task.task_source == "profile_generated" else "✍️ Manual"]
            if task.retrieval_sources:
                source_badges.append("📚 RAG")
            source_badge_text = " | ".join(source_badges)

            st.markdown(
                f"{status_icon} {priority_colors[task.priority]} **{task.title}**{recurring_badge}  "
                f"<span style='font-size:0.85em; color:#555;'>[{source_badge_text}]</span>",
                unsafe_allow_html=True,
            )

            details_parts = [f"{task.duration} min", f"{task.priority.name} priority", f"🐾 {task.pet_name}"]
            if task.preferred_time:
                details_parts.append(f"⏰ Prefers {task.preferred_time.strftime('%I:%M %p')}")
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

            duration_pct = min(task.duration / 120, 1.0)
            st.progress(duration_pct, text=f"{task.duration} minutes")

        with col2:
            if not task.completed and st.button("✓ Complete", key=f"task_complete_{task.id}"):
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

if not show_completed:
    completed_tasks = [t for t in owner.get_all_tasks() if t.completed]
    if completed_tasks:
        with st.expander(f"📋 Completed Tasks ({len(completed_tasks)})"):
            tasks_data = [
                {
                    "Pet": task.pet_name,
                    "Task": task.title,
                    "Priority": task.priority.name,
                    "Date": task.scheduled_date.strftime("%Y-%m-%d") if task.scheduled_date else "-",
                }
                for task in completed_tasks
            ]
            st.table(tasks_data)
