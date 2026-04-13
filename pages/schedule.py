import datetime
from datetime import timedelta

import streamlit as st

from pawpal_system import Scheduler
from ui_shared import display_task_card, init_app_state, routine_ready, sync_workflow_phase

st.title("📅 Schedule View")
owner = init_app_state()
sync_workflow_phase(owner)

if not routine_ready(owner):
    st.caption("Schedule visualization will unlock after owner and pet setup on Home.")

handoff_summary = st.session_state.get("schedule_handoff_summary")
if handoff_summary:
    st.info(
        "Ready to schedule for "
        f"{handoff_summary['pet_name']}: "
        f"{handoff_summary['included']} included, "
        f"{handoff_summary['skipped']} skipped, "
        f"{handoff_summary['locked']} locked time preferences."
    )

tab1, tab2 = st.tabs(["📋 Daily Schedule", "📅 Weekly Calendar"])

with tab1:
    trigger_daily_generation = st.button("Generate Daily Schedule", key="schedule_generate_daily")
    if st.session_state.auto_generate_daily_schedule:
        trigger_daily_generation = True
        st.session_state.auto_generate_daily_schedule = False

    if trigger_daily_generation:
        all_tasks = owner.get_all_tasks()
        if not all_tasks:
            st.warning("⚠️ Please add at least one task before generating a schedule.")
        else:
            scheduler = Scheduler(owner)

            warnings = scheduler.detect_preferred_time_conflicts()
            if warnings:
                st.warning("⚠️ Preferred Time Conflicts Detected:")
                for warning in warnings:
                    if "Same pet conflict" in warning:
                        st.error(warning)
                    else:
                        st.info(warning)
                st.caption("The scheduler will try to resolve these conflicts automatically.")

            schedule = scheduler.generate_schedule()
            reliability = scheduler.get_reliability_report()
            st.session_state.schedule_handoff_summary = {
                "pet_name": handoff_summary["pet_name"] if handoff_summary else "All pets",
                "included": reliability["scheduled_tasks"],
                "skipped": len(reliability["unscheduled_tasks"]),
                "locked": handoff_summary["locked"] if handoff_summary else 0,
            }

            st.success("✅ Schedule generated!")
            st.markdown("### Today's Schedule")
            st.text(scheduler.explain_schedule())

            with st.expander("Decision Metadata"):
                for item in schedule:
                    task = item["task"]
                    confidence = item.get("confidence_score", 0.0)
                    rules = item.get("applied_rules", [])
                    sources = item.get("retrieval_sources", [])
                    guidance_profile = item.get("guidance_profile", {})
                    source_text = ", ".join(sources) if sources else "-"
                    energy_level = guidance_profile.get("energy_level", "-")
                    exercise_types = guidance_profile.get("preferred_exercise_types", [])
                    exercise_text = ", ".join(exercise_types) if exercise_types else "-"
                    st.caption(
                        f"{task.title}: confidence={confidence:.2f} | "
                        f"rules={', '.join(rules) if rules else '-'} | "
                        f"sources={source_text} | "
                        f"energy={energy_level} | "
                        f"exercise={exercise_text}"
                    )

            with st.expander("Reliability Summary", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Overall Confidence", f"{reliability['overall_confidence']:.2f}")
                with col2:
                    st.metric("Scheduled", reliability["scheduled_tasks"])
                with col3:
                    st.metric("Unscheduled", len(reliability["unscheduled_tasks"]))

                if reliability["guardrail_warnings"]:
                    st.warning("Guardrail warnings:")
                    for warning in reliability["guardrail_warnings"]:
                        st.caption(f"- {warning}")

            conflicts = scheduler.detect_conflicts()
            if conflicts:
                st.error("⚠️ Final schedule conflicts detected:")
                for conflict in conflicts:
                    st.write(f"- {conflict}")
            else:
                st.success("✓ No scheduling conflicts in final schedule!")

with tab2:
    st.markdown("### Weekly Calendar View")

    col1, col2 = st.columns(2)
    with col1:
        scheduler_helper = Scheduler(owner)
        monday, _sunday = scheduler_helper.get_week_date_range()
        start_date = st.date_input("Week starting (Monday)", value=monday, key="schedule_week_start")
    with col2:
        end_date = start_date + timedelta(days=6)
        st.info(f"Showing: {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}")

    if st.button("Generate Weekly Calendar", key="schedule_generate_weekly"):
        scheduler = Scheduler(owner)
        weekly_data = {}
        for i in range(7):
            current_day = start_date + timedelta(days=i)
            schedule = scheduler.generate_schedule(target_date=current_day)
            weekly_data[current_day] = schedule

        st.markdown("---")

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        cols = st.columns(7)
        for idx, col in enumerate(cols):
            with col:
                day = start_date + timedelta(days=idx)
                st.markdown(f"**{day_names[idx]}**")
                st.caption(day.strftime("%b %d"))

        cols = st.columns(7)
        for idx, col in enumerate(cols):
            day = start_date + timedelta(days=idx)
            schedule = weekly_data[day]
            with col:
                if not schedule:
                    st.caption("_No tasks_")
                else:
                    scheduled_tasks = [item for item in schedule if item["time"] is not None]
                    if not scheduled_tasks:
                        st.caption("_No tasks_")
                    else:
                        for item in scheduled_tasks:
                            display_task_card(item, compact=True)
                            st.divider()

        st.markdown("---")
        st.markdown("### Weekly Summary")

        total_tasks = sum(len(schedule) for schedule in weekly_data.values())
        total_scheduled = sum(
            sum(1 for item in schedule if item["time"] is not None) for schedule in weekly_data.values()
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Tasks", total_tasks)
        with col2:
            st.metric("Scheduled", total_scheduled)
        with col3:
            st.metric("Unscheduled", total_tasks - total_scheduled)
