import datetime
from datetime import timedelta

import streamlit as st

from pawpal_system import Scheduler
from ui_shared import (
    compute_schedule_input_fingerprint,
    display_task_card,
    init_app_state,
    mark_schedule_stale,
    render_sidebar_guidance,
    routine_ready,
    sync_workflow_phase,
    update_schedule_fingerprint,
)

st.title("📅 Schedule View")
owner = init_app_state()
sync_workflow_phase(owner)
render_sidebar_guidance("Schedule", owner)

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

schedule_state = st.session_state.schedule_state
current_fingerprint = compute_schedule_input_fingerprint(owner)
if schedule_state.get("input_fingerprint") != current_fingerprint:
    mark_schedule_stale()
    update_schedule_fingerprint(owner)


def _format_generated_at(ts: datetime.datetime | None) -> str:
    if ts is None:
        return "-"
    return ts.strftime("%b %d, %I:%M %p")


def _generate_daily_result(target_date: datetime.date | None = None) -> dict:
    scheduler = Scheduler(owner)
    warnings = scheduler.detect_preferred_time_conflicts()
    schedule = scheduler.generate_schedule(target_date=target_date)
    reliability = scheduler.get_reliability_report()
    conflicts = scheduler.detect_conflicts()

    return {
        "date": target_date or datetime.date.today(),
        "schedule": schedule,
        "reliability": reliability,
        "warnings": warnings,
        "conflicts": conflicts,
        "explanation": scheduler.explain_schedule(),
        "generated_at": datetime.datetime.now(),
        "input_fingerprint": current_fingerprint,
    }


def _render_daily_result(daily_result: dict) -> None:
    st.markdown("### Today's Schedule")

    warnings = daily_result.get("warnings", [])
    if warnings:
        st.warning("⚠️ Preferred Time Conflicts Detected:")
        for warning in warnings:
            if "Same pet conflict" in warning:
                st.error(warning)
            else:
                st.info(warning)
        st.caption("The scheduler will try to resolve these conflicts automatically.")

    st.text(daily_result.get("explanation", ""))

    schedule = daily_result.get("schedule", [])
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

    reliability = daily_result.get("reliability", {})
    with st.expander("Reliability Summary", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Overall Confidence", f"{reliability.get('overall_confidence', 0.0):.2f}")
        with col2:
            st.metric("Scheduled", reliability.get("scheduled_tasks", 0))
        with col3:
            st.metric("Unscheduled", len(reliability.get("unscheduled_tasks", [])))

        if reliability.get("guardrail_warnings"):
            st.warning("Guardrail warnings:")
            for warning in reliability["guardrail_warnings"]:
                st.caption(f"- {warning}")

    conflicts = daily_result.get("conflicts", [])
    if conflicts:
        st.error("⚠️ Final schedule conflicts detected:")
        for conflict in conflicts:
            st.write(f"- {conflict}")
    else:
        st.success("✓ No scheduling conflicts in final schedule!")

tab1, tab2 = st.tabs(["📋 Daily Schedule", "📅 Weekly Calendar"])

with tab1:
    daily_cached = schedule_state.get("daily", {})
    has_daily_cache = daily_cached.get("schedule") is not None

    col1, col2 = st.columns(2)
    with col1:
        trigger_daily_generation = st.button("Generate Daily Schedule", key="schedule_generate_daily")
    with col2:
        refresh_daily = st.button(
            "Refresh Daily Schedule",
            key="schedule_refresh_daily",
            disabled=not has_daily_cache,
        )

    if st.session_state.auto_generate_daily_schedule:
        trigger_daily_generation = True
        st.session_state.auto_generate_daily_schedule = False

    if trigger_daily_generation or refresh_daily:
        all_tasks = owner.get_all_tasks()
        if not all_tasks:
            st.warning("⚠️ Please add at least one task before generating a schedule.")
        else:
            daily_result = _generate_daily_result()
            reliability = daily_result.get("reliability", {})
            schedule_state["daily"] = daily_result
            schedule_state["stale"] = False
            schedule_state["input_fingerprint"] = current_fingerprint

            st.session_state.schedule_handoff_summary = {
                "pet_name": handoff_summary["pet_name"] if handoff_summary else "All pets",
                "included": reliability["scheduled_tasks"],
                "skipped": len(reliability["unscheduled_tasks"]),
                "locked": handoff_summary["locked"] if handoff_summary else 0,
            }

            st.success("✅ Schedule generated!")

    daily_cached = schedule_state.get("daily", {})
    has_daily_cache = daily_cached.get("schedule") is not None
    if has_daily_cache:
        generated_at = _format_generated_at(daily_cached.get("generated_at"))
        if schedule_state.get("stale"):
            st.warning(
                f"⚠️ Schedule may be stale (last generated {generated_at}). "
                "Review task edits and click Refresh Daily Schedule."
            )
        else:
            st.caption(f"Using cached daily schedule generated {generated_at}.")
        _render_daily_result(daily_cached)

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

    weekly_cached = schedule_state.get("weekly", {})
    has_weekly_cache = bool(weekly_cached.get("daily_results"))

    col1, col2 = st.columns(2)
    with col1:
        trigger_weekly_generation = st.button("Generate Weekly Calendar", key="schedule_generate_weekly")
    with col2:
        refresh_weekly = st.button(
            "Refresh Weekly Calendar",
            key="schedule_refresh_weekly",
            disabled=not has_weekly_cache,
        )

    if trigger_weekly_generation or refresh_weekly:
        scheduler = Scheduler(owner)
        weekly_data = {}
        for i in range(7):
            current_day = start_date + timedelta(days=i)
            schedule = scheduler.generate_schedule(target_date=current_day)
            weekly_data[current_day] = schedule

        total_tasks = sum(len(schedule) for schedule in weekly_data.values())
        total_scheduled = sum(
            sum(1 for item in schedule if item["time"] is not None) for schedule in weekly_data.values()
        )
        weekly_summary = {
            "total_tasks": total_tasks,
            "scheduled_tasks": total_scheduled,
            "unscheduled_tasks": total_tasks - total_scheduled,
        }

        schedule_state["weekly"] = {
            "start_date": start_date,
            "end_date": end_date,
            "daily_results": weekly_data,
            "summary": weekly_summary,
            "generated_at": datetime.datetime.now(),
            "input_fingerprint": current_fingerprint,
        }
        schedule_state["stale"] = False
        schedule_state["input_fingerprint"] = current_fingerprint

    weekly_cached = schedule_state.get("weekly", {})
    show_weekly_cache = (
        bool(weekly_cached.get("daily_results"))
        and weekly_cached.get("start_date") == start_date
        and weekly_cached.get("end_date") == end_date
    )

    if show_weekly_cache:
        weekly_data = weekly_cached["daily_results"]
        generated_at = _format_generated_at(weekly_cached.get("generated_at"))
        if schedule_state.get("stale"):
            st.warning(
                f"⚠️ Weekly calendar may be stale (last generated {generated_at}). "
                "Review changes and click Refresh Weekly Calendar."
            )
        else:
            st.caption(f"Using cached weekly calendar generated {generated_at}.")

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
        weekly_summary = weekly_cached.get("summary", {})
        total_tasks = weekly_summary.get("total_tasks", 0)
        total_scheduled = weekly_summary.get("scheduled_tasks", 0)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Tasks", total_tasks)
        with col2:
            st.metric("Scheduled", total_scheduled)
        with col3:
            st.metric("Unscheduled", weekly_summary.get("unscheduled_tasks", 0))
    elif has_weekly_cache and weekly_cached.get("start_date") != start_date:
        st.caption("A cached weekly calendar exists for a different week. Click Generate Weekly Calendar to load this week.")
