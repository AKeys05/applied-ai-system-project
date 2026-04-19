"""
Groq API integration for global day planning in PawPal+.

Takes the full task list + per-task RAG guidance and produces an optimal
daily schedule via a single Groq call with JSON mode.

Falls back gracefully to None on API unavailability or any call failure.
Results are cached in-memory by a fingerprint of task IDs + locked times + date.
"""
import hashlib
import json
import os
from datetime import date, time
from typing import Dict

_client = None
_plan_cache: dict[str, dict] = {}

_PLANNER_SYSTEM = (
    "You are a daily schedule planner for pet care.\n"
    "Rules you must follow:\n"
    "1. LOCKED tasks must be scheduled at their exact specified time — no deviation allowed.\n"
    "2. Preferred times are strong hints; try to honor them within ±30 minutes if possible.\n"
    "3. RAG guidance windows are soft constraints; prefer scheduling within them when possible.\n"
    "4. Leave at least 15 minutes between consecutive tasks for the same pet.\n"
    "5. Never schedule tasks before the owner availability start or after the availability end.\n"
    "6. Spread same-type tasks (walks, meals, play sessions) evenly across the day.\n"
    "7. Schedule higher-priority tasks earlier in the day when no other constraints apply.\n"
    "8. If a task truly cannot fit within the available window, set scheduled_time to null.\n"
    "Always respond with valid JSON only."
)

_RESPONSE_SCHEMA = (
    "Return a JSON object with exactly this structure:\n"
    "{\n"
    '  "assignments": [\n'
    "    {\n"
    '      "task_id": "<exact task ID from input>",\n'
    '      "scheduled_time": "<HH:MM 24-hour> or null if unschedulable",\n'
    '      "reason": "<one sentence explaining the placement decision>"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "Include one entry per task in the input list."
)


def _get_client():
    global _client
    if _client is None:
        try:
            from groq import Groq
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                print("[ai_planner] No GROQ_API_KEY found in environment")
                return None
            _client = Groq(api_key=api_key)
            print("[ai_planner] Groq client initialized OK")
        except ImportError:
            print("[ai_planner] groq package not installed")
            return None
    return _client


def _parse_hhmm(s) -> time | None:
    if not s:
        return None
    try:
        h, m = map(int, s.split(":"))
        return time(h, m)
    except Exception:
        return None


def _build_plan_cache_key(tasks: list, target_date: date) -> str:
    fingerprints = sorted(
        f"{t.id}:{t.preferred_time.strftime('%H:%M') if t.locked_preferred_time and t.preferred_time else 'free'}"
        for t in tasks
    )
    raw = "|".join(fingerprints) + f"|date:{target_date.isoformat()}"
    return hashlib.md5(raw.encode()).hexdigest()


def _build_availability_text(owner) -> str:
    windows = getattr(owner, "availability_windows", [])
    if not windows:
        return "No availability restriction (tasks may be placed 06:00–22:00)"
    lines = [f"{s.strftime('%H:%M')} – {e.strftime('%H:%M')}" for s, e in windows]
    return "Owner available: " + ", ".join(lines)


def _build_task_line(task, guidance: dict) -> str:
    parts = [
        f"[task_id={task.id}]",
        f'"{task.title}"',
        f"pet: {task.pet_name}",
        f"{task.duration} min",
        f"priority: {task.priority.name}",
    ]

    if task.locked_preferred_time and task.preferred_time:
        parts.append(f"LOCKED at {task.preferred_time.strftime('%H:%M')}")
    elif task.preferred_time:
        parts.append(f"preferred: {task.preferred_time.strftime('%H:%M')}")

    earliest = guidance.get("earliest_start")
    latest = guidance.get("latest_end")
    if guidance.get("rag_active") and (earliest or latest):
        window_parts = []
        if earliest:
            window_parts.append(earliest.strftime("%H:%M"))
        if latest:
            window_parts.append(latest.strftime("%H:%M"))
        parts.append(f"RAG window: {' – '.join(window_parts)}")

    return " | ".join(parts)


def _build_user_message(tasks: list, task_guidance: dict, owner, target_date: date) -> str:
    lines = [
        f"Date: {target_date.isoformat()}",
        "",
        _build_availability_text(owner),
        "",
        f"Tasks to schedule ({len(tasks)} total):",
    ]
    for task in tasks:
        guidance = task_guidance.get(task.id, {})
        lines.append("  " + _build_task_line(task, guidance))

    lines += [
        "",
        "Scheduling reminders:",
        "- LOCKED tasks must use their exact specified time.",
        "- 15-minute minimum gap between tasks for the same pet.",
        "- Spread walks and meals evenly across the day.",
        "- Fit all tasks within the availability window.",
        "",
        _RESPONSE_SCHEMA,
    ]
    return "\n".join(lines)


def plan_daily_schedule(
    tasks: list,
    task_guidance: Dict[str, Dict],
    owner,
    target_date: date | None = None,
) -> Dict[str, dict] | None:
    """
    Call Groq to produce a globally-optimal daily schedule.

    Returns:
        Dict mapping task.id -> {"time": datetime.time | None, "reason": str},
        or None if the API is unavailable or the call fails entirely.
    """
    if not tasks:
        return {}

    client = _get_client()
    if not client:
        return None

    effective_date = target_date or date.today()
    cache_key = _build_plan_cache_key(tasks, effective_date)
    if cache_key in _plan_cache:
        return _plan_cache[cache_key]

    user_message = _build_user_message(tasks, task_guidance, owner, effective_date)

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _PLANNER_SYSTEM},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            max_tokens=1024,
        )
        data = json.loads(response.choices[0].message.content)
        assignments = data.get("assignments", [])
        if not isinstance(assignments, list):
            return None
        result: Dict[str, dict] = {}
        for a in assignments:
            task_id = a.get("task_id")
            if task_id:
                result[task_id] = {
                    "time": _parse_hhmm(a.get("scheduled_time")),
                    "reason": a.get("reason", ""),
                }
        _plan_cache[cache_key] = result
        return result
    except Exception as e:
        import traceback
        print(f"[ai_planner] ERROR: {e}")
        traceback.print_exc()
        return None


def clear_plan_cache() -> None:
    _plan_cache.clear()
