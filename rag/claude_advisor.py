"""
Claude API integration for pet care scheduling advice.

Calls claude-haiku with tool use to get structured scheduling recommendations.
Falls back gracefully to None if the API key is missing or any call fails.
Results are cached in-memory by (species, breed, age_category, activity_level,
normalized_task_title) to avoid redundant API calls within a session.
"""
import os
import re
from typing import Optional

_client = None
_cache: dict[str, dict] = {}

_TOOL = {
    "name": "provide_scheduling_advice",
    "description": "Provide structured pet care scheduling recommendations.",
    "input_schema": {
        "type": "object",
        "properties": {
            "priority_boost": {
                "type": "number",
                "description": "Priority boost 0.0–1.0. Higher means schedule sooner.",
            },
            "window_start": {
                "type": "string",
                "description": "Recommended earliest start time HH:MM (24-hour), or null.",
            },
            "window_end": {
                "type": "string",
                "description": "Recommended latest end time HH:MM (24-hour), or null.",
            },
            "reasons": {
                "type": "array",
                "items": {"type": "string"},
                "description": "1–3 concise reasons for the recommendations.",
            },
            "exercise_types": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Suitable activity types for this pet and task.",
            },
            "energy_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "very_high"],
                "description": "Pet's typical energy level for this task.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence in this advice, 0.0–1.0.",
            },
        },
        "required": ["priority_boost", "reasons", "confidence"],
    },
}

_SYSTEM = (
    "You are a veterinary-informed pet care scheduling assistant. "
    "Given a pet's profile and relevant breed guidelines, provide practical, "
    "concise scheduling advice. Use your breed and species knowledge to fill "
    "gaps when retrieved guidelines are limited."
)


def _get_client():
    global _client
    if _client is None:
        try:
            from anthropic import Anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                return None
            _client = Anthropic(api_key=api_key)
        except ImportError:
            return None
    return _client


def _normalize_title(title: str) -> str:
    """Collapse 'Walk #1' / 'Walk #2' to 'walk' so they share a cache entry."""
    return re.sub(r"\s*#\d+$", "", title).strip().lower()


def _age_category(age_years: Optional[float], species: str) -> str:
    if age_years is None:
        return "adult"
    thresholds = {"dog": (1.0, 8.0), "cat": (1.0, 10.0)}
    young, senior = thresholds.get(species.lower(), (1.0, 8.0))
    if age_years < young:
        return "puppy_kitten"
    if age_years >= senior:
        return "senior"
    return "adult"


def get_scheduling_advice(
    species: str,
    breed: str,
    age_years: Optional[float],
    activity_level: str,
    task_title: str,
    task_duration: int,
    retrieved_context: list[dict],
) -> Optional[dict]:
    """
    Call Claude to get structured scheduling advice for one pet task.
    Returns the tool-use input dict, or None if unavailable or failed.
    """
    client = _get_client()
    if not client:
        return None

    age_cat = _age_category(age_years, species)
    cache_key = "|".join([
        species.lower(),
        (breed or "mixed").lower(),
        age_cat,
        (activity_level or "medium").lower(),
        _normalize_title(task_title),
    ])
    if cache_key in _cache:
        return _cache[cache_key]

    if retrieved_context:
        context_lines = [
            f"- [{e.get('source_type', 'general')}] {e.get('reason', '')}"
            for e in retrieved_context
            if e.get("reason")
        ]
        context_text = "\n".join(context_lines) or "No specific rules retrieved."
    else:
        context_text = "No specific rules retrieved — use your general breed/species knowledge."

    age_display = f"{age_years} years ({age_cat})" if age_years is not None else f"unknown ({age_cat})"
    user_message = (
        f"Pet profile:\n"
        f"- Species: {species}\n"
        f"- Breed: {breed or 'Mixed/Unknown'}\n"
        f"- Age: {age_display}\n"
        f"- Activity level: {activity_level}\n\n"
        f"Task to schedule: {task_title} ({task_duration} min)\n\n"
        f"Retrieved breed/species guidelines:\n{context_text}\n\n"
        f"Provide scheduling advice for this task."
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "provide_scheduling_advice"},
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == "provide_scheduling_advice":
                _cache[cache_key] = block.input
                return block.input
        return None
    except Exception:
        return None


def clear_cache() -> None:
    """Clear the in-memory advice cache (useful for testing)."""
    _cache.clear()
