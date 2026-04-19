import datetime

import streamlit as st

from pawpal_system import Frequency, Priority, RoutineProfile, ScheduleConstraint, Scheduler, Task
from ui_shared import (
    init_app_state,
    mark_schedule_stale,
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

# Compute early so review renders above the profile form
generated_tasks = [
    t for t in owner.get_tasks_for_pet(routine_pet_name) if t.task_source == "profile_generated"
]

# One-shot notice shown on the render immediately after generation
if notice := st.session_state.pop("_tb_generation_notice", None):
    st.success(notice)

# ── STEP INDICATOR & REVIEW (shown first when tasks exist) ────────────────
review_step_key = f"task_review_step_{routine_pet_name}"
if review_step_key not in st.session_state:
    st.session_state[review_step_key] = 1
# Migrate legacy string values written by the old radio widget
if isinstance(st.session_state[review_step_key], str):
    st.session_state[review_step_key] = 3 if "Confirm" in st.session_state[review_step_key] else 1

if generated_tasks:
    current_step = st.session_state[review_step_key]

    st.markdown("#### Review Generated Tasks")

    # Visual step indicator — not interactive, navigation via buttons only
    ind_col1, ind_col2, ind_col3, ind_spacer = st.columns([2, 2, 2, 2])
    with ind_col1:
        st.markdown("**① Include/Skip**" if current_step == 1 else "① Include/Skip")
    with ind_col2:
        st.markdown("**② Timing**" if current_step == 2 else "② Timing")
    with ind_col3:
        st.markdown("**③ Confirm**" if current_step == 3 else "③ Confirm")
    st.markdown("---")

    # ────── STEP 1: Include/Skip Form ──────
    if current_step == 1:
        st.caption("Select which tasks to include in the schedule.")
        task_includes = {}
        with st.form("task_review_include"):
            for task in generated_tasks:
                with st.container(border=True):
                    info_col, ctrl_col = st.columns([4, 1])
                    with info_col:
                        st.markdown(f"**{task.title}**")
                        st.caption(f"{task.duration} min • {task.priority.name} priority")
                    with ctrl_col:
                        include = st.checkbox(
                            "Include",
                            value=not task.skipped,
                            key=f"r_inc_{task.id}",
                        )
                    task_includes[task.id] = include

            save_includes = st.form_submit_button("Save & Continue to Timing →", type="primary")
            if save_includes:
                for task in generated_tasks:
                    owner.edit_task(task.id, skipped=not task_includes[task.id])
                st.session_state[review_step_key] = 2
                st.rerun()

    # ────── STEP 2: Timing Configuration (Fully Reactive) ──────
    elif current_step == 2:
        st.caption("Configure timing preferences for included tasks.")
        included_tasks = [t for t in generated_tasks if not t.skipped]

        if not included_tasks:
            st.info("No tasks included. Go back to select at least one task.")
            if st.button("← Back to Include/Skip", key="task_step2_back"):
                st.session_state[review_step_key] = 1
                st.rerun()
        else:
            task_timing = {}
            for task in included_tasks:
                with st.container(border=True):
                    title_col, ctrl_col = st.columns([3, 2])

                    with title_col:
                        st.markdown(f"**{task.title}**")
                        st.caption(f"{task.duration} min • {task.priority.name}")

                    with ctrl_col:
                        modes = ["No preference", "Flexible", "Locked"]
                        if task.preferred_time is None:
                            initial_mode = "No preference"
                        elif task.locked_preferred_time:
                            initial_mode = "Locked"
                        else:
                            initial_mode = "Flexible"

                        mode = st.selectbox(
                            "Timing",
                            modes,
                            index=modes.index(initial_mode),
                            key=f"timing_mode_{task.id}",
                        )

                        # Fully reactive: show/hide time input based on current mode value
                        if mode == "No preference":
                            st.caption("No time set")
                            time_val = None
                        else:
                            time_val = st.time_input(
                                "Preferred time",
                                value=task.preferred_time or datetime.time(8, 0),
                                key=f"timing_time_{task.id}",
                            )

                        task_timing[task.id] = (mode, time_val)

            timing_col1, timing_col2 = st.columns(2)
            with timing_col1:
                if st.button("← Back to Include/Skip", key="task_step2_back_button"):
                    st.session_state[review_step_key] = 1
                    st.rerun()
            with timing_col2:
                if st.button("Save & Continue to Confirm →", key="task_step2_continue", type="primary"):
                    for task in included_tasks:
                        mode, time_val = task_timing[task.id]
                        update_fields = {}
                        if mode == "No preference":
                            update_fields["preferred_time"] = None
                            update_fields["locked_preferred_time"] = False
                        elif mode == "Flexible":
                            update_fields["preferred_time"] = time_val
                            update_fields["locked_preferred_time"] = False
                        else:  # Locked
                            update_fields["preferred_time"] = time_val
                            update_fields["locked_preferred_time"] = True
                        owner.edit_task(task.id, **update_fields)
                    mark_schedule_stale()
                    st.session_state[review_step_key] = 3
                    st.rerun()

    # ────── STEP 3: Confirm ──────
    else:  # current_step == 3
        included_count = len([t for t in generated_tasks if not t.skipped])
        skipped_count = len([t for t in generated_tasks if t.skipped])
        locked_count = len([t for t in generated_tasks if t.locked_preferred_time])
        flexible_count = len([
            t for t in generated_tasks
            if t.preferred_time is not None and not t.locked_preferred_time
        ])

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Included", included_count)
        with c2:
            st.metric("Skipped", skipped_count)
        with c3:
            st.metric("Locked", locked_count)
        with c4:
            st.metric("Flexible", flexible_count)

        review_scheduler = Scheduler(owner)
        conflict_warnings = review_scheduler.detect_preferred_time_conflicts()
        if conflict_warnings:
            st.warning("Potential preferred-time conflicts detected:")
            for warning in conflict_warnings:
                st.caption(f"- {warning}")

        st.caption("Ready to generate schedule.")

        back_col, generate_col = st.columns([1, 2])
        with back_col:
            if st.button("← Back to Timing", key="task_back_to_step2"):
                st.session_state[review_step_key] = 2
                st.rerun()
        with generate_col:
            if st.button("Generate Schedule →", key="task_continue_to_schedule", type="primary"):
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

# ── PROFILE FORM (collapsed when tasks already exist) ─────────────────────
def _time_default(field: str, fallback: datetime.time) -> datetime.time:
    return profile_defaults.get(field, fallback)

expander_label = "⚙️ Regenerate Routine" if generated_tasks else "⚙️ Generate Routine"
with st.expander(expander_label, expanded=not bool(generated_tasks)):
    copy_candidates = [
        p for p in st.session_state.last_routine_profiles if p != routine_pet_name
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

    summary = getattr(owner, "last_generation_summary", {})
    if summary and summary.get("pet_name") == routine_pet_name:
        s1, s2 = st.columns(2)
        with s1:
            st.metric("Last created", summary.get("created_count", 0))
        with s2:
            st.metric("Last removed", summary.get("removed_count", 0))

    with st.form("task_routine_builder_form"):
        st.caption("Set daily care preferences. PawPal+ will auto-generate tasks from this profile.")

        col1, col2, col3 = st.columns(3)
        with col1:
            walks_per_day = st.number_input("Walks per day", min_value=0, max_value=6, value=int(profile_defaults.get("walks_per_day", 1)), step=1, key=f"task_walks_per_day_{routine_pet_name}")
            meals_per_day = st.number_input("Meals per day", min_value=0, max_value=6, value=int(profile_defaults.get("meals_per_day", 2)), step=1, key=f"task_meals_per_day_{routine_pet_name}")
        with col2:
            play_sessions = st.number_input("Play/enrichment sessions", min_value=0, max_value=6, value=int(profile_defaults.get("play_sessions_per_day", 1)), step=1, key=f"task_play_sessions_{routine_pet_name}")
            grooming_per_week = st.number_input("Grooming sessions/week", min_value=0, max_value=7, value=int(profile_defaults.get("grooming_sessions_per_week", 0)), step=1, key=f"task_grooming_per_week_{routine_pet_name}")
        with col3:
            med_doses = st.number_input("Medication doses/day", min_value=0, max_value=6, value=int(profile_defaults.get("med_doses", 0)), step=1, key=f"task_med_doses_{routine_pet_name}")

        st.markdown("**Preferred windows**")
        w1, w2 = st.columns(2)
        with w1:
            walk_window_start = st.time_input("Walk window start", value=_time_default("walk_window_start", datetime.time(7, 0)), key=f"task_walk_window_start_{routine_pet_name}")
            meal_window_start = st.time_input("Meal window start", value=_time_default("meal_window_start", datetime.time(7, 0)), key=f"task_meal_window_start_{routine_pet_name}")
            play_window_start = st.time_input("Play window start", value=_time_default("play_window_start", datetime.time(8, 0)), key=f"task_play_window_start_{routine_pet_name}")
        with w2:
            walk_window_end = st.time_input("Walk window end", value=_time_default("walk_window_end", datetime.time(10, 0)), key=f"task_walk_window_end_{routine_pet_name}")
            meal_window_end = st.time_input("Meal window end", value=_time_default("meal_window_end", datetime.time(19, 0)), key=f"task_meal_window_end_{routine_pet_name}")
            play_window_end = st.time_input("Play window end", value=_time_default("play_window_end", datetime.time(20, 0)), key=f"task_play_window_end_{routine_pet_name}")

        medication_times = []
        default_med_times = profile_defaults.get("medication_times", [])
        if med_doses > 0:
            st.markdown("**Medication times**")
            for idx in range(int(med_doses)):
                default_med_time = datetime.time(8 + idx, 0)
                if idx < len(default_med_times):
                    default_med_time = default_med_times[idx]
                medication_times.append(st.time_input(f"Medication time #{idx + 1}", value=default_med_time, key=f"task_med_time_{routine_pet_name}_{idx}"))

        if generated_tasks:
            st.warning("⚠️ Generating will replace existing tasks and reset all review preferences.")

        regenerate_mode = st.checkbox("Replace previously generated profile tasks for this pet", value=bool(profile_defaults.get("regenerate_mode", True)), key=f"task_regenerate_mode_{routine_pet_name}")
        form_submitted = st.form_submit_button("Generate Routine Tasks")

        if form_submitted:
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
                routine_pet_name, profile, replace_existing=regenerate_mode,
            )
            if success:
                mark_schedule_stale()
                st.session_state._tb_generation_notice = (
                    f"✅ {tasks_created} tasks generated for {routine_pet_name}. "
                    "Configure them above before scheduling."
                )
                st.session_state.workflow_phase = "review"
                st.session_state[f"task_review_step_{routine_pet_name}"] = 1
                st.rerun()
            else:
                st.error(f"❌ Could not generate routine tasks: {error}")

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
            mark_schedule_stale()
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
    priority_colors = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
    for task in all_tasks:
        edit_key = f"_tb_editing_{task.id}"
        confirm_key = f"_tb_confirm_delete_{task.id}"

        col1, col2 = st.columns([4, 1])
        with col1:
            recurring_badge = f" `{task.frequency.value}`" if task.frequency else ""
            status_icon = "✅" if task.completed else "⭕"
            source_badges = ["🎯 Profile" if task.task_source == "profile_generated" else "✍️ Manual"]
            if task.retrieval_sources:
                source_badges.append("📚 RAG")
            source_badge_text = " | ".join(source_badges)

            st.markdown(
                f"{status_icon} {priority_colors.get(task.priority.name, '⚪')} **{task.title}**{recurring_badge}  "
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
            if not task.completed and st.button("Mark Done", key=f"task_complete_{task.id}"):
                success, next_task = owner.complete_task(task.id)
                if success:
                    mark_schedule_stale()
                    if next_task:
                        st.success(f"✅ Completed! Next: {next_task.scheduled_date}")
                    else:
                        st.success("✅ Task completed!")
                    st.rerun()
                else:
                    st.error("❌ Failed to complete task")

            if st.button("Edit", key=f"task_edit_btn_{task.id}"):
                for k in list(st.session_state.keys()):
                    if k.startswith("_tb_editing_") and k != edit_key:
                        del st.session_state[k]
                st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                st.rerun()

            if not st.session_state.get(confirm_key):
                if st.button("Delete", key=f"task_delete_btn_{task.id}"):
                    st.session_state[confirm_key] = True
                    st.rerun()
            else:
                st.warning("Delete?")
                yes_col, no_col = st.columns(2)
                with yes_col:
                    if st.button("Yes", key=f"task_delete_yes_{task.id}"):
                        owner.remove_task(task.id)
                        st.session_state.pop(confirm_key, None)
                        st.session_state.pop(edit_key, None)
                        mark_schedule_stale()
                        st.rerun()
                with no_col:
                    if st.button("No", key=f"task_delete_no_{task.id}"):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()

        if st.session_state.get(edit_key):
            with st.container(border=True):
                st.markdown(f"**Edit: {task.title}**")
                e1, e2, e3 = st.columns(3)
                with e1:
                    new_title = st.text_input("Title", value=task.title, key=f"edit_title_{task.id}")
                with e2:
                    new_duration = st.number_input(
                        "Duration (min)", min_value=1, max_value=240,
                        value=task.duration, key=f"edit_duration_{task.id}"
                    )
                with e3:
                    priority_names = ["low", "medium", "high"]
                    current_priority = task.priority.name.lower()
                    new_priority_str = st.selectbox(
                        "Priority", priority_names,
                        index=priority_names.index(current_priority),
                        key=f"edit_priority_{task.id}",
                    )

                use_pref_time = st.checkbox(
                    "Set preferred time",
                    value=task.preferred_time is not None,
                    key=f"edit_use_pref_{task.id}",
                )
                new_preferred_time = None
                if use_pref_time:
                    new_preferred_time = st.time_input(
                        "Preferred time",
                        value=task.preferred_time or datetime.time(8, 0),
                        key=f"edit_pref_time_{task.id}",
                    )

                save_col, cancel_col = st.columns(2)
                with save_col:
                    if st.button("Save Changes", key=f"edit_save_{task.id}"):
                        priority_map = {"low": Priority.LOW, "medium": Priority.MEDIUM, "high": Priority.HIGH}
                        owner.edit_task(
                            task.id,
                            title=new_title,
                            duration=int(new_duration),
                            priority=priority_map[new_priority_str],
                            preferred_time=new_preferred_time,
                        )
                        st.session_state.pop(edit_key, None)
                        mark_schedule_stale()
                        st.rerun()
                with cancel_col:
                    if st.button("Cancel", key=f"edit_cancel_{task.id}"):
                        st.session_state.pop(edit_key, None)
                        st.rerun()

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
