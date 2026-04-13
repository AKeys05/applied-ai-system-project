import os
import sys
from datetime import time

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from pawpal_system import Owner, Pet, Task, Priority, Scheduler


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


def signature(schedule):
    return [(item["task"].title, item["time"], item.get("confidence_score", 0.0)) for item in schedule]


def run_consistency_check(name: str, scheduler: Scheduler) -> dict:
    first = scheduler.generate_schedule()
    first_sig = signature(first)
    second = scheduler.generate_schedule()
    second_sig = signature(second)

    report = scheduler.get_reliability_report()
    return {
        "name": name,
        "consistent": first_sig == second_sig,
        "scheduled": report["scheduled_tasks"],
        "total": report["total_tasks"],
        "overall_confidence": report["overall_confidence"],
        "warnings": len(report["guardrail_warnings"]),
    }


def main():
    scenarios = [
        ("Border Collie Morning Priority", scenario_border_collie()),
        ("French Bulldog Constraint", scenario_french_bulldog()),
        ("Multi-Pet Collision", scenario_multi_pet_collision()),
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
            f"confidence {result['overall_confidence']:.2f} | "
            f"warnings {result['warnings']}"
        )

    if failures > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
