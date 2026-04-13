import os
import sys
from datetime import time

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from pawpal_system import Owner, Pet, Task, Priority, RoutineProfile, Scheduler


def scenario_border_collie() -> Scheduler:
    owner = Owner("Jordan")
    owner.set_timezone("US/Pacific")
    owner.add_availability_window(time(7, 0), time(12, 0))

    dog = Pet(name="Mochi", species="Dog", breed="Border Collie", activity_level="high")
    owner.add_pet(dog)

    owner.add_task(
        "Mochi",
        Task(title="Morning Walk", duration=45, priority=Priority.HIGH, pet_name="Mochi", time_constraint="before 09:00"),
    )
    owner.add_task(
        "Mochi",
        Task(title="Breakfast", duration=15, priority=Priority.HIGH, pet_name="Mochi"),
    )
    owner.add_task(
        "Mochi",
        Task(title="Enrichment", duration=30, priority=Priority.MEDIUM, pet_name="Mochi"),
    )

    return Scheduler(owner)


def scenario_french_bulldog() -> Scheduler:
    owner = Owner("Jordan")
    owner.add_availability_window(time(7, 0), time(21, 0))

    dog = Pet(name="Poppy", species="Dog", breed="French Bulldog", activity_level="medium")
    owner.add_pet(dog)

    owner.add_task(
        "Poppy",
        Task(title="Medication", duration=10, priority=Priority.HIGH, pet_name="Poppy", time_constraint="after 08:00"),
    )
    owner.add_task(
        "Poppy",
        Task(title="Breakfast", duration=15, priority=Priority.HIGH, pet_name="Poppy"),
    )
    owner.add_task(
        "Poppy",
        Task(title="Short Walk", duration=30, priority=Priority.MEDIUM, pet_name="Poppy"),
    )

    return Scheduler(owner)


def scenario_multi_pet_collision() -> Scheduler:
    owner = Owner("Jordan")
    owner.add_availability_window(time(7, 0), time(12, 0))

    dog = Pet(name="Rex", species="Dog")
    cat = Pet(name="Luna", species="Cat")
    owner.add_pet(dog)
    owner.add_pet(cat)

    owner.add_task(
        "Rex",
        Task(title="Dog Walk", duration=30, priority=Priority.HIGH, pet_name="Rex", preferred_time=time(8, 0)),
    )
    owner.add_task(
        "Luna",
        Task(title="Cat Feeding", duration=15, priority=Priority.HIGH, pet_name="Luna", preferred_time=time(8, 0)),
    )

    return Scheduler(owner)


def scenario_profile_generated_border_collie() -> Scheduler:
    owner = Owner("Jordan")
    owner.set_timezone("US/Pacific")
    owner.add_availability_window(time(7, 0), time(12, 0))

    dog = Pet(name="Mochi", species="Dog", breed="Border Collie", activity_level="high")
    owner.add_pet(dog)

    profile = RoutineProfile(
        walks_per_day=1,
        meals_per_day=2,
        play_sessions_per_day=1,
        walk_window_start=time(6, 30),
        walk_window_end=time(9, 30),
        meal_window_start=time(7, 0),
        meal_window_end=time(19, 0),
        play_window_start=time(8, 0),
        play_window_end=time(20, 0),
    )
    success, _created, error = owner.generate_tasks_from_profile("Mochi", profile)
    if not success:
        raise RuntimeError(f"Failed to generate profile tasks for evaluation: {error}")

    return Scheduler(owner)


def signature(schedule):
    return [(item["task"].title, item["time"], item.get("confidence_score", 0.0)) for item in schedule]


def run_consistency_check(name: str, scheduler: Scheduler) -> dict:
    first = scheduler.generate_schedule(enable_rag=True)
    first_sig = signature(first)
    second = scheduler.generate_schedule(enable_rag=True)
    second_sig = signature(second)

    rag_schedule = scheduler.generate_schedule(enable_rag=True)
    rag_sig = signature(rag_schedule)
    rag_report = scheduler.get_reliability_report()

    baseline_schedule = scheduler.generate_schedule(enable_rag=False)
    baseline_sig = signature(baseline_schedule)
    baseline_report = scheduler.get_reliability_report()

    changed_count = 0
    baseline_map = {item[0]: item[1] for item in baseline_sig}
    for title, scheduled_time, _ in rag_sig:
        if baseline_map.get(title) != scheduled_time:
            changed_count += 1

    rag_impact_delta = rag_report["scheduled_ratio"] - baseline_report["scheduled_ratio"]

    return {
        "name": name,
        "consistent": first_sig == second_sig,
        "scheduled": rag_report["scheduled_tasks"],
        "total": rag_report["total_tasks"],
        "scheduled_ratio": rag_report["scheduled_ratio"],
        "overall_confidence": rag_report["overall_confidence"],
        "warnings": len(rag_report["guardrail_warnings"]),
        "citation_coverage": rag_report["citation_coverage"],
        "constraint_respect": rag_report["constraint_respect"],
        "rag_active_tasks": rag_report["rag_active_tasks"],
        "rag_impact_tasks": changed_count,
        "rag_impact_delta": round(rag_impact_delta, 2),
    }


def main():
    scenarios = [
        ("Border Collie Morning Priority", scenario_border_collie()),
        ("French Bulldog Constraint", scenario_french_bulldog()),
        ("Multi-Pet Collision", scenario_multi_pet_collision()),
        ("Profile-Generated Border Collie", scenario_profile_generated_border_collie()),
    ]

    results = [run_consistency_check(name, scheduler) for name, scheduler in scenarios]

    print("=== Phase 1 Evaluation ===")
    failures = 0
    for result in results:
        status = "PASS" if result["consistent"] else "FAIL"
        if not result["consistent"]:
            failures += 1
        print(
            f"[{status}] {result['name']} | "
            f"scheduled {result['scheduled']}/{result['total']} | "
            f"scheduled_ratio {result['scheduled_ratio']:.2f} | "
            f"confidence {result['overall_confidence']:.2f} | "
            f"warnings {result['warnings']} | "
            f"citation_coverage {result['citation_coverage']:.2f} | "
            f"constraint_respect {result['constraint_respect']:.2f} | "
            f"rag_active_tasks {result['rag_active_tasks']} | "
            f"rag_impact_tasks {result['rag_impact_tasks']} | "
            f"rag_impact_delta {result['rag_impact_delta']:.2f}"
        )

    if failures > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
