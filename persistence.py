import json
from datetime import date, time
from pathlib import Path
from typing import Any, Optional

from pawpal_system import Frequency, Owner, Pet, Priority, ScheduleConstraint, Task

SAVE_PATH = Path(__file__).parent / "pawpal_save.json"


def _time_to_str(t: Optional[time]) -> Optional[str]:
    return t.strftime("%H:%M") if t else None


def _str_to_time(s: Optional[str]) -> Optional[time]:
    if not s:
        return None
    h, m = map(int, s.split(":"))
    return time(h, m)


def _date_to_str(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def _str_to_date(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s else None


def _constraint_to_dict(sc: ScheduleConstraint) -> dict:
    return {
        "earliest_start": _time_to_str(sc.earliest_start),
        "latest_end": _time_to_str(sc.latest_end),
        "hard_constraint": sc.hard_constraint,
        "source": sc.source,
    }


def _dict_to_constraint(d: dict) -> ScheduleConstraint:
    return ScheduleConstraint(
        earliest_start=_str_to_time(d.get("earliest_start")),
        latest_end=_str_to_time(d.get("latest_end")),
        hard_constraint=d.get("hard_constraint", True),
        source=d.get("source", "user"),
    )


def _task_to_dict(task: Task) -> dict:
    return {
        "title": task.title,
        "duration": task.duration,
        "priority": task.priority.name,
        "pet_name": task.pet_name,
        "id": task.id,
        "is_recurring": task.is_recurring,
        "preferred_time": _time_to_str(task.preferred_time),
        "time_constraint": task.time_constraint,
        "schedule_constraint": _constraint_to_dict(task.schedule_constraint),
        "completed": task.completed,
        "frequency": task.frequency.value if task.frequency else None,
        "scheduled_date": _date_to_str(task.scheduled_date),
        "parent_task_id": task.parent_task_id,
        "retrieval_sources": list(task.retrieval_sources),
        "task_source": task.task_source,
        "skipped": task.skipped,
        "locked_preferred_time": task.locked_preferred_time,
    }


def _dict_to_task(d: dict) -> Task:
    return Task(
        title=d["title"],
        duration=d["duration"],
        priority=Priority[d["priority"]],
        pet_name=d["pet_name"],
        id=d["id"],
        is_recurring=d.get("is_recurring", False),
        preferred_time=_str_to_time(d.get("preferred_time")),
        time_constraint=d.get("time_constraint"),
        schedule_constraint=_dict_to_constraint(d.get("schedule_constraint", {})),
        completed=d.get("completed", False),
        frequency=Frequency(d["frequency"]) if d.get("frequency") else None,
        scheduled_date=_str_to_date(d.get("scheduled_date")),
        parent_task_id=d.get("parent_task_id"),
        retrieval_sources=d.get("retrieval_sources", []),
        task_source=d.get("task_source", "manual"),
        skipped=d.get("skipped", False),
        locked_preferred_time=d.get("locked_preferred_time", False),
    )


def _pet_to_dict(pet: Pet) -> dict:
    return {
        "name": pet.name,
        "species": pet.species,
        "breed": pet.breed,
        "age_years": pet.age_years,
        "activity_level": pet.activity_level,
        "preferences": dict(pet.preferences),
        "restrictions": list(pet.restrictions),
        "tasks": [_task_to_dict(t) for t in pet.tasks],
    }


def _dict_to_pet(d: dict) -> Pet:
    pet = Pet(
        name=d["name"],
        species=d["species"],
        breed=d.get("breed", ""),
        age_years=d.get("age_years"),
        activity_level=d.get("activity_level", "medium"),
        preferences=d.get("preferences", {}),
        restrictions=d.get("restrictions", []),
    )
    for task_dict in d.get("tasks", []):
        pet.tasks.append(_dict_to_task(task_dict))
    return pet


def owner_to_dict(owner: Owner) -> dict:
    return {
        "name": owner.name,
        "timezone": owner.timezone,
        "availability_windows": [
            [_time_to_str(s), _time_to_str(e)]
            for s, e in owner.availability_windows
        ],
        "constraints": dict(owner.constraints),
        "pets": [_pet_to_dict(p) for p in owner.pets.values()],
    }


def owner_from_dict(d: dict) -> Owner:
    owner = Owner(d["name"])
    owner.timezone = d.get("timezone", "Local")
    owner.availability_windows = [
        (_str_to_time(s), _str_to_time(e))
        for s, e in d.get("availability_windows", [])
    ]
    owner.constraints = d.get("constraints", {})
    for pet_dict in d.get("pets", []):
        pet = _dict_to_pet(pet_dict)
        owner.add_pet(pet)
    return owner


def _serialize_profile_value(key: str, value: Any) -> Any:
    if isinstance(value, time):
        return _time_to_str(value)
    if isinstance(value, list):
        return [_serialize_profile_value("", item) for item in value]
    return value


_PROFILE_TIME_FIELDS = {
    "walk_window_start", "walk_window_end",
    "meal_window_start", "meal_window_end",
    "play_window_start", "play_window_end",
}


def _deserialize_profile_value(key: str, value: Any) -> Any:
    if key in _PROFILE_TIME_FIELDS:
        return _str_to_time(value)
    if key == "medication_times":
        return [_str_to_time(t) for t in (value or [])]
    return value


def save_state(
    owner: Owner,
    last_routine_profiles: dict,
    save_path: Path = SAVE_PATH,
) -> bool:
    """Serialize owner and routine profiles to JSON. Returns True on success."""
    try:
        profiles_serialized = {
            pet_name: {k: _serialize_profile_value(k, v) for k, v in profile.items()}
            for pet_name, profile in last_routine_profiles.items()
        }
        payload = {
            "version": 1,
            "owner": owner_to_dict(owner),
            "last_routine_profiles": profiles_serialized,
        }
        save_path.write_text(json.dumps(payload, indent=2))
        return True
    except Exception:
        return False


def load_state(
    save_path: Path = SAVE_PATH,
) -> Optional[tuple[Owner, dict]]:
    """Load owner and routine profiles from JSON. Returns None if no save exists or on error."""
    try:
        if not save_path.exists():
            return None
        data = json.loads(save_path.read_text())
        owner = owner_from_dict(data["owner"])
        raw_profiles = data.get("last_routine_profiles", {})
        profiles = {
            pet_name: {k: _deserialize_profile_value(k, v) for k, v in profile.items()}
            for pet_name, profile in raw_profiles.items()
        }
        return owner, profiles
    except Exception:
        return None
