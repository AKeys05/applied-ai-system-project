"""
Groq API integration for pet care scheduling advice.

Calls llama-3.3-70b-versatile with JSON mode to get structured scheduling
recommendations. Falls back gracefully to None if the API key is missing
or any call fails. Results are cached in-memory by
(species, breed, age_category, activity_level, normalized_task_title).
"""
import json
import os
import re
from typing import Optional

_client = None
_cache: dict[str, dict] = {}

_SYSTEM = (
    "You are a veterinary-informed pet care scheduling assistant. "
    "Given a pet's profile and relevant breed guidelines, provide practical, "
    "concise scheduling advice. Use your breed and species knowledge to fill "
    "gaps when retrieved guidelines are limited. "
    "Always respond with valid JSON only."
)

_RESPONSE_SCHEMA = (
    "Return a JSON object with exactly these fields:\n"
    "- priority_boost: number 0.0-1.0 (how urgently to schedule this task)\n"
    "- window_start: string HH:MM 24-hour or null (recommended earliest start)\n"
    "- window_end: string HH:MM 24-hour or null (recommended latest end)\n"
    "- reasons: array of 1-3 short strings explaining the recommendations\n"
    "- exercise_types: array of strings (suitable activity types, empty if not applicable)\n"
    "- energy_level: one of 'low', 'medium', 'high', 'very_high' or null\n"
    "- confidence: number 0.0-1.0 (confidence in this advice)"
)


def _get_client():
    global _client
    if _client is None:
        try:
            from groq import Groq
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                return None
            _client = Groq(api_key=api_key)
        except ImportError:
            return None
    return _client


def _normalize_title(title: str) -> str:
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
    Call Groq to get structured scheduling advice for one pet task.
    Returns a dict with scheduling fields, or None if unavailable or failed.
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
        f"Provide scheduling advice for this task.\n\n"
        f"{_RESPONSE_SCHEMA}"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            max_tokens=512,
        )
        data = json.loads(response.choices[0].message.content)
        if "priority_boost" in data and "confidence" in data:
            _cache[cache_key] = data
            return data
        return None
    except Exception:
        return None


def clear_cache() -> None:
    _cache.clear()
