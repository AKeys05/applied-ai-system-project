import datetime
from datetime import timedelta

import streamlit as st

from petplanify_system import Scheduler
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


def _rag_status_label(rag_active_tasks: int, total_tasks: int) -> str:
    if total_tasks == 0:
        return "No tasks"
    ratio = rag_active_tasks / total_tasks
    if ratio >= 0.75:
        return "High"
    if ratio >= 0.4:
        return "Moderate"
    if ratio > 0:
        return "Low"
    return "None"


def _guidance_badge(rag_active: bool, guidance_source: str) -> str:
    if guidance_source in ("claude", "ai_planned") and rag_active:
        return "🤖 AI-Powered"
    if guidance_source == "ai_planned":
        return "🤖 AI Planned"
    if not rag_active:
        return "⚪ No Guidance"
    return "🔍 Rules Match"


_PRIORITY_ICON = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}

_RULE_LABELS: dict[str, str] = {
    "ai_planned": "AI day planner",
    "preferred_time": "preferred time honored",
    "preferred_time_fallback": "rescheduled from preferred time",
    "priority_sort": "placed by priority",
    "time_constraint": "time constraint applied",
    "owner_availability": "within owner hours",
    "pet_restrictions": "pet restrictions considered",
    "rag_guidance": "AI guidance applied",
    "rag_fallback_low_confidence": "AI guidance low confidence",
    "locked_preferred_time": "locked to preferred time",
}


def _readable_rules(rules: list) -> list:
    return [_RULE_LABELS.get(r, r) for r in rules if r not in ("unscheduled", "locked_preferred_time")]


def _clean_sources(sources: list) -> list:
    cleaned = []
    for s in sources:
        parts = s.split(":")
        cleaned.append(parts[1].replace("_", " ").title() if len(parts) >= 2 else s)
    return cleaned


def _confidence_label(score: float) -> str:
    pct = int(score * 100)
    if score >= 0.8:
        return f"Confidence {pct}% · High"
    if score >= 0.6:
        return f"Confidence {pct}% · Fair"
    return f"Confidence {pct}% · Low"


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

    reliability = daily_result.get("reliability", {})
    total_tasks = reliability.get("total_tasks", 0)
    rag_active_tasks = reliability.get("rag_active_tasks", 0)
    rag_fallback_count = reliability.get("rag_fallback_count", 0)
    citation_coverage = reliability.get("citation_coverage", 0.0)

    schedule = daily_result.get("schedule", [])
    ai_powered_count = sum(
        1 for item in schedule
        if item.get("guidance_profile", {}).get("rag_active")
        and item.get("guidance_profile", {}).get("guidance_source") in ("claude", "ai_planned")
    )

    ai_planned_count = sum(
        1 for item in schedule
        if "ai_planned" in item.get("applied_rules", [])
    )

    st.markdown("#### AI Guidance Status")
    s1, s2, s3, s4, s5 = st.columns(5)
    with s1:
        st.metric("AI Planned", f"{ai_planned_count}/{total_tasks}")
    with s2:
        st.metric("AI-Powered Tasks", f"{ai_powered_count}/{total_tasks}")
    with s3:
        st.metric("Guidance Influence", _rag_status_label(rag_active_tasks, total_tasks))
    with s4:
        st.metric("Fallback Count", rag_fallback_count)
    with s5:
        st.metric("Citation Coverage", f"{citation_coverage:.2f}")

    if schedule:
        st.markdown("#### Daily Task Panels")
        scheduled_items = [item for item in schedule if item.get("time") is not None]
        unscheduled_items = [item for item in schedule if item.get("time") is None]

        for item in scheduled_items:
            task = item["task"]
            guidance_profile = item.get("guidance_profile", {})
            rag_active = bool(guidance_profile.get("rag_active"))
            retrieval_confidence = float(guidance_profile.get("retrieval_confidence", 0.0))
            confidence_score = float(item.get("confidence_score", 0.0))
            rules = item.get("applied_rules", [])
            sources = item.get("retrieval_sources", [])
            reason_text = item.get("reason", "")
            energy_level = guidance_profile.get("energy_level") or ""
            exercise_types = guidance_profile.get("preferred_exercise_types", [])
            guidance_source = guidance_profile.get("guidance_source", "retriever")
            priority_icon = _PRIORITY_ICON.get(task.priority.name, "")

            with st.container(border=True):
                # ── Header row ────────────────────────────────────────────
                h1, h2, h3, h4 = st.columns([2, 5, 2, 2])
                with h1:
                    st.markdown(f"### {item['time'].strftime('%I:%M %p')}")
                with h2:
                    st.markdown(f"**{task.title}**")
                    st.caption(
                        f"{priority_icon} {task.priority.name} priority"
                        f"  ·  {task.duration} min"
                        f"  ·  🐾 {task.pet_name}"
                    )
                with h3:
                    st.markdown(_guidance_badge(rag_active, guidance_source))
                    st.caption(_confidence_label(confidence_score))
                with h4:
                    if task.completed:
                        st.success("✅ Done")
                    else:
                        if st.button("Mark Done", key=f"sched_done_{task.id}"):
                            owner.complete_task(task.id)
                            mark_schedule_stale()
                            st.rerun()

                st.divider()

                # ── Scheduling reason ─────────────────────────────────────
                st.markdown("**Why this time**")
                # Strip the verbose AI guidance suffix from the reason — it lives in the expander
                short_reason = reason_text.split(". Guidance:")[0].split(". Energy profile:")[0]
                st.write(short_reason)

                # ── Details expander ──────────────────────────────────────
                with st.expander("Details"):
                    sched_col, ai_col = st.columns(2)
                    with sched_col:
                        st.markdown("**Scheduling**")
                        readable = _readable_rules(rules)
                        st.caption(f"Rules applied: {', '.join(readable) if readable else '—'}")
                        st.caption(f"Schedule confidence: {_confidence_label(confidence_score)}")
                    with ai_col:
                        st.markdown("**AI Guidance**")
                        st.caption(
                            f"Source: {_guidance_badge(rag_active, guidance_source)}"
                        )
                        if rag_active:
                            st.caption(f"Retrieval confidence: {retrieval_confidence:.0%}")
                            if sources:
                                st.caption(f"Sources: {', '.join(_clean_sources(sources))}")
                            if energy_level:
                                st.caption(f"Energy level: {energy_level}")
                            if exercise_types:
                                st.caption(f"Exercise types: {', '.join(exercise_types)}")
                        else:
                            st.caption("No guidance was applied for this task.")

        if unscheduled_items:
            st.markdown("#### Unscheduled Tasks")
            for item in unscheduled_items:
                task = item["task"]
                priority_icon = _PRIORITY_ICON.get(task.priority.name, "")
                with st.container(border=True):
                    h1, h2 = st.columns([5, 2])
                    with h1:
                        st.markdown(f"**{task.title}**")
                        st.caption(
                            f"{priority_icon} {task.priority.name} priority"
                            f"  ·  {task.duration} min"
                            f"  ·  🐾 {task.pet_name}"
                        )
                    with h2:
                        st.markdown("⏸ Unscheduled")
                    st.divider()
                    st.markdown("**Why not scheduled**")
                    st.write(item.get("reason", "Could not be scheduled due to time or availability constraints."))

    with st.expander("Narrative Summary"):
        st.text(daily_result.get("explanation", ""))

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
        conflict_lines = ["**⚠️ Final schedule conflicts detected:**"]
        conflict_lines += [f"- {c}" for c in conflicts]
        st.error("\n".join(conflict_lines))
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
        weekly_data = {}
        for i in range(7):
            current_day = start_date + timedelta(days=i)
            weekly_data[current_day] = _generate_daily_result(target_date=current_day)

        total_tasks = sum(
            len(r.get("schedule", [])) for r in weekly_data.values()
        )
        total_scheduled = sum(
            sum(1 for item in r.get("schedule", []) if item["time"] is not None)
            for r in weekly_data.values()
        )
        total_conflicts = sum(
            len(r.get("conflicts", [])) for r in weekly_data.values()
        )
        weekly_summary = {
            "total_tasks": total_tasks,
            "scheduled_tasks": total_scheduled,
            "unscheduled_tasks": total_tasks - total_scheduled,
            "total_conflicts": total_conflicts,
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
            daily_result = weekly_data[day]
            day_schedule = daily_result.get("schedule", [])
            day_conflicts = daily_result.get("conflicts", [])
            with col:
                if day_conflicts:
                    st.caption("⚠️ Conflict")
                scheduled_tasks = [item for item in day_schedule if item["time"] is not None]
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

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Tasks", total_tasks)
        with col2:
            st.metric("Scheduled", total_scheduled)
        with col3:
            st.metric("Unscheduled", weekly_summary.get("unscheduled_tasks", 0))
        with col4:
            st.metric("Days w/ Conflicts", weekly_summary.get("total_conflicts", 0))
    elif has_weekly_cache and weekly_cached.get("start_date") != start_date:
        st.caption("A cached weekly calendar exists for a different week. Click Generate Weekly Calendar to load this week.")
