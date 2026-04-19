from petplanify_system import Owner, Pet, Task, Scheduler, Priority
from datetime import time

if __name__ == "__main__":
	# Create an owner
	owner = Owner("Alex")
	print(f"Welcome to PawPal+, {owner.name}!\n")

	# Create pets
	dog = Pet(
		name="Buddy",
		species="Dog",
		preferences={"favorite_toy": "tennis ball", "likes_walks": True},
		restrictions=["no_midday_walks"]
	)

	cat = Pet(
		name="Whiskers",
		species="Cat",
		preferences={"favorite_food": "tuna", "indoor_only": True},
		restrictions=[]
	)

	# Add pets to owner
	owner.add_pet(dog)
	owner.add_pet(cat)
	print(f"Registered pets: {dog.name} (Dog) and {cat.name} (Cat)\n")

	# Create tasks OUT OF ORDER (by time) to test sorting
	# Note: Adding tasks with various times, not in chronological order

	dog_playtime = Task(
		title="Play Fetch",
		duration=20,
		priority=Priority.MEDIUM,
		pet_name="Buddy",
		preferred_time=time(15, 0)  # 3:00 PM
	)

	dog_walk = Task(
		title="Morning Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Buddy",
		preferred_time=time(8, 0),  # 8:00 AM
		time_constraint="before 09:00"
	)

	cat_grooming = Task(
		title="Brush Fur",
		duration=15,
		priority=Priority.LOW,
		pet_name="Whiskers",
		preferred_time=time(12, 0)  # 12:00 PM (Noon)
	)

	dog_feeding = Task(
		title="Feed Breakfast",
		duration=15,
		priority=Priority.HIGH,
		pet_name="Buddy",
		preferred_time=time(7, 0),  # 7:00 AM
	)

	cat_feeding = Task(
		title="Feed Breakfast",
		duration=10,
		priority=Priority.HIGH,
		pet_name="Whiskers",
		preferred_time=time(6, 30),  # 6:30 AM
		time_constraint="before 08:00"
	)

	dog_evening_walk = Task(
		title="Evening Walk",
		duration=25,
		priority=Priority.MEDIUM,
		pet_name="Buddy",
		preferred_time=time(18, 30)  # 6:30 PM
	)

	# Add tasks to pets (in random order)
	dog.add_task(dog_playtime)
	dog.add_task(dog_walk)
	dog.add_task(dog_feeding)
	dog.add_task(dog_evening_walk)
	cat.add_task(cat_grooming)
	cat.add_task(cat_feeding)

	print("Tasks added successfully!\n")

	# Display all tasks before scheduling
	print("=" * 50)
	print("ALL TASKS (Added Out of Order)")
	print("=" * 50)
	owner.display_tasks()
	print()

	# ===== DEMONSTRATE SORTING AND FILTERING METHODS =====
	print("=" * 50)
	print("TESTING SORTING AND FILTERING METHODS")
	print("=" * 50)
	print()

	# Get all tasks
	all_tasks = owner.get_all_tasks()

	# 1. Test sorting by time
	print("1️⃣  SORTED BY TIME (using Task.sort_by_time):")
	print("-" * 50)
	sorted_tasks = Task.sort_by_time(all_tasks)
	for task in sorted_tasks:
		time_str = task.preferred_time.strftime("%I:%M %p") if task.preferred_time else "No time set"
		print(f"  {time_str:15} | {task.pet_name:10} | {task.title}")
	print()

	# 2. Test filtering by completion status
	print("2️⃣  FILTER BY COMPLETION STATUS:")
	print("-" * 50)
	incomplete_tasks = Task.filter_by_completion(all_tasks, completed=False)
	print(f"  Incomplete tasks: {len(incomplete_tasks)}")
	for task in incomplete_tasks:
		print(f"    ○ {task.title} ({task.pet_name})")
	print()

	# Mark some tasks as completed to test filtering
	dog_feeding.completed = True
	cat_feeding.completed = True

	completed_tasks = Task.filter_by_completion(all_tasks, completed=True)
	print(f"  Completed tasks: {len(completed_tasks)}")
	for task in completed_tasks:
		print(f"    ✓ {task.title} ({task.pet_name})")
	print()

	# 3. Test filtering by pet
	print("3️⃣  FILTER BY PET (using Task.filter_by_pet):")
	print("-" * 50)
	buddy_tasks = Task.filter_by_pet(all_tasks, "Buddy")
	print(f"  Buddy's tasks: {len(buddy_tasks)}")
	for task in buddy_tasks:
		status = "✓" if task.completed else "○"
		print(f"    {status} {task.title}")

	whiskers_tasks = Task.filter_by_pet(all_tasks, "Whiskers")
	print(f"\n  Whiskers' tasks: {len(whiskers_tasks)}")
	for task in whiskers_tasks:
		status = "✓" if task.completed else "○"
		print(f"    {status} {task.title}")
	print()

	# 4. Test combined filtering
	print("4️⃣  COMBINED FILTERING (using Task.filter_tasks):")
	print("-" * 50)
	buddy_incomplete = Task.filter_tasks(all_tasks, pet_name="Buddy", completed=False)
	print(f"  Buddy's incomplete tasks: {len(buddy_incomplete)}")
	for task in buddy_incomplete:
		time_str = task.preferred_time.strftime("%I:%M %p") if task.preferred_time else "No time"
		print(f"    ○ {task.title} at {time_str}")
	print()

	# 5. Sort and filter combined
	print("5️⃣  SORTED + FILTERED (Buddy's incomplete tasks by time):")
	print("-" * 50)
	buddy_incomplete_sorted = Task.sort_by_time(buddy_incomplete)
	for task in buddy_incomplete_sorted:
		time_str = task.preferred_time.strftime("%I:%M %p") if task.preferred_time else "No time"
		print(f"  {time_str:15} | {task.title}")
	print()

	print("✓ All sorting and filtering tests complete!\n")

	# ===== DEMONSTRATE CONFLICT DETECTION =====
	print("=" * 60)
	print("TESTING CONFLICT DETECTION")
	print("=" * 60)
	print()

	# Scenario 1: Same pet conflict - critical warning
	print("Scenario 1: Same Pet Conflict (Critical)")
	print("-" * 60)

	# Create a new owner for conflict demo to avoid interfering with existing tasks
	conflict_owner = Owner("Jordan")
	conflict_dog = Pet(name="Rex", species="Dog")
	conflict_cat = Pet(name="Mittens", species="Cat")
	conflict_owner.add_pet(conflict_dog)
	conflict_owner.add_pet(conflict_cat)

	walk1 = Task(
		title="Morning Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0)  # 8:00-8:30 AM
	)

	walk2 = Task(
		title="Dog Park Visit",
		duration=45,
		priority=Priority.MEDIUM,
		pet_name="Rex",
		preferred_time=time(8, 15)  # 8:15-9:00 AM (overlaps!)
	)

	conflict_owner.add_task("Rex", walk1)
	conflict_owner.add_task("Rex", walk2)

	conflict_scheduler = Scheduler(conflict_owner)
	warnings = conflict_scheduler.detect_preferred_time_conflicts()

	print(f"Added 2 tasks for Rex with overlapping preferred times:")
	print(f"  - Morning Walk: 8:00 AM (30 min)")
	print(f"  - Dog Park Visit: 8:15 AM (45 min)")
	print()
	print("Conflict warnings:")
	for warning in warnings:
		print(f"  {warning}")
	print()

	# Scenario 2: Different pet conflict - informational warning
	print("\nScenario 2: Multi-Pet Conflict (Informational)")
	print("-" * 60)

	cat_feeding_conflict = Task(
		title="Cat Breakfast",
		duration=10,
		priority=Priority.HIGH,
		pet_name="Mittens",
		preferred_time=time(8, 0)  # Same time as dog walk
	)

	conflict_owner.add_task("Mittens", cat_feeding_conflict)

	conflict_scheduler = Scheduler(conflict_owner)
	warnings = conflict_scheduler.detect_preferred_time_conflicts()

	print(f"Added Cat Breakfast at 8:00 AM (same as Dog's Morning Walk)")
	print()
	print("All conflict warnings:")
	for warning in warnings:
		print(f"  {warning}")
	print()

	# Scenario 3: Generate schedule and see how conflicts are resolved
	print("\nScenario 3: Scheduler Resolution")
	print("-" * 60)

	conflict_schedule = conflict_scheduler.generate_schedule()

	print("The scheduler automatically resolves conflicts:")
	print()
	for item in conflict_schedule:
		if item['time']:
			task = item['task']
			scheduled_time = item['time'].strftime('%I:%M %p')
			preferred = task.preferred_time.strftime('%I:%M %p') if task.preferred_time else "None"
			print(f"  {scheduled_time:12} | {task.pet_name:10} | {task.title}")
			if task.preferred_time and item['time'] != task.preferred_time:
				print(f"               (preferred: {preferred}, rescheduled)")
		else:
			print(f"  NOT SCHEDULED | {item['pet_name']:10} | {item['task'].title}")
	print()

	# Verify final schedule has no conflicts
	conflict_check = conflict_scheduler.detect_conflicts()
	print(f"Final schedule conflicts: {len(conflict_check)}")
	print()

	# Scenario 4: No conflicts - sequential tasks
	print("\nScenario 4: No Conflicts (Sequential Tasks)")
	print("-" * 60)

	owner_seq = Owner("Taylor")
	dog_seq = Pet(name="Max", species="Dog")
	owner_seq.add_pet(dog_seq)

	task1 = Task(
		title="Morning Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Max",
		preferred_time=time(7, 0)  # 7:00-7:30
	)

	task2 = Task(
		title="Breakfast",
		duration=15,
		priority=Priority.HIGH,
		pet_name="Max",
		preferred_time=time(7, 30)  # 7:30-7:45 (no overlap)
	)

	owner_seq.add_task("Max", task1)
	owner_seq.add_task("Max", task2)

	scheduler_seq = Scheduler(owner_seq)
	warnings_seq = scheduler_seq.detect_preferred_time_conflicts()

	print(f"Added 2 sequential tasks for Max:")
	print(f"  - Morning Walk: 7:00 AM (30 min)")
	print(f"  - Breakfast: 7:30 AM (15 min)")
	print()
	print(f"Conflict warnings: {len(warnings_seq)}")
	if len(warnings_seq) == 0:
		print("  ✓ No conflicts detected - tasks are perfectly sequential!")
	print()

	print("✓ All conflict detection tests complete!\n")

	# Create scheduler and generate schedule for original owner
	scheduler = Scheduler(owner)
	print("=" * 50)
	print("GENERATING TODAY'S SCHEDULE...")
	print("=" * 50)
	print()

	schedule = scheduler.generate_schedule()

	# Print the schedule with explanations
	print(scheduler.explain_schedule())

	# Check for any conflicts
	conflicts = scheduler.detect_conflicts()
	if conflicts:
		print("⚠️  CONFLICTS DETECTED:")
		for conflict in conflicts:
			print(f"  - {conflict}")
	else:
		print("✓ No scheduling conflicts detected!")
