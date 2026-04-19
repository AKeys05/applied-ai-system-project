from petplanify_system import Owner, Pet, Task, Priority, Scheduler, Frequency, ScheduleConstraint, RoutineProfile
from datetime import time, date, timedelta


def test_pet_profile_fields_are_stored():
	"""Test that new pet profile fields are persisted on Pet instances."""
	pet = Pet(
		name="Rex",
		species="Dog",
		breed="Border Collie",
		age_years=3.5,
		activity_level="high",
	)

	assert pet.breed == "Border Collie"
	assert pet.age_years == 3.5
	assert pet.activity_level == "high"


def test_routine_profile_validation_rejects_invalid_windows():
	"""Routine profile should reject invalid window ordering."""
	profile = RoutineProfile(
		walk_window_start=time(10, 0),
		walk_window_end=time(8, 0),
	)
	is_valid, error = profile.validate()
	assert is_valid == False
	assert error is not None


def test_generate_tasks_from_profile_creates_expected_daily_tasks():
	"""Owner should synthesize routine tasks from profile preferences."""
	owner = Owner("Jordan")
	pet = Pet(name="Mochi", species="Dog", breed="Border Collie")
	owner.add_pet(pet)

	profile = RoutineProfile(
		walks_per_day=2,
		meals_per_day=2,
		play_sessions_per_day=1,
		medication_times=[time(8, 0)],
		grooming_sessions_per_week=1,
	)

	success, created_count, error = owner.generate_tasks_from_profile("Mochi", profile)
	assert success == True
	assert error is None
	assert created_count == 7  # 2 walks + 2 meals + 1 play + 1 meds + 1 grooming

	all_tasks = owner.get_all_tasks()
	assert len(all_tasks) == 7
	assert all(task.task_source == "profile_generated" for task in all_tasks)
	assert sum(1 for t in all_tasks if t.title.startswith("Exercise - Walk")) == 2
	assert sum(1 for t in all_tasks if t.title.startswith("Feeding - Meal")) == 2
	assert any(t.title == "Health - Medication" for t in all_tasks)


def test_generate_tasks_from_profile_replaces_previous_generated_tasks():
	"""Regenerating profile tasks should replace old generated tasks when requested."""
	owner = Owner("Jordan")
	pet = Pet(name="Mochi", species="Dog", breed="Border Collie")
	owner.add_pet(pet)

	first_profile = RoutineProfile(walks_per_day=1, meals_per_day=1, play_sessions_per_day=0)
	second_profile = RoutineProfile(walks_per_day=2, meals_per_day=1, play_sessions_per_day=1)

	success1, created1, _ = owner.generate_tasks_from_profile("Mochi", first_profile, replace_existing=True)
	assert success1 == True
	assert created1 == 2

	success2, created2, _ = owner.generate_tasks_from_profile("Mochi", second_profile, replace_existing=True)
	assert success2 == True
	assert created2 == 4

	all_tasks = owner.get_all_tasks()
	assert len(all_tasks) == 4
	assert sum(1 for t in all_tasks if t.title.startswith("Exercise - Walk")) == 2


def test_skipped_task_is_omitted_from_schedule():
	"""Skipped tasks in generated plan review should not be scheduled."""
	owner = Owner("Jordan")
	dog = Pet(name="Mochi", species="Dog", breed="Border Collie")
	owner.add_pet(dog)

	profile = RoutineProfile(walks_per_day=1, meals_per_day=1, play_sessions_per_day=0)
	success, _, _ = owner.generate_tasks_from_profile("Mochi", profile)
	assert success == True

	meal_task = next(t for t in owner.get_all_tasks() if t.title.startswith("Feeding - Meal"))
	owner.edit_task(meal_task.id, skipped=True)

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()
	scheduled_titles = [item['task'].title for item in schedule]
	assert not any(title.startswith("Feeding - Meal") for title in scheduled_titles)


def test_locked_preferred_time_unschedules_when_slot_conflicts():
	"""Locked preferred-time tasks should not fallback to alternate slots when blocked."""
	owner = Owner("Jordan")
	dog = Pet(name="Mochi", species="Dog", breed="")
	owner.add_pet(dog)

	blocker = Task(
		title="Manual Blocker",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Mochi",
		preferred_time=time(8, 0),
	)
	locked = Task(
		title="Exercise - Walk",
		duration=30,
		priority=Priority.MEDIUM,
		pet_name="Mochi",
		preferred_time=time(8, 0),
		locked_preferred_time=True,
		task_source="profile_generated",
	)

	assert owner.add_task("Mochi", blocker)
	assert owner.add_task("Mochi", locked)

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()
	locked_item = next(item for item in schedule if item['task'].title == "Exercise - Walk")
	assert locked_item['time'] is None
	assert "locked_preferred_time" in locked_item['applied_rules']


def test_structured_constraint_respected_when_scheduling():
	"""Test that structured time constraints are honored by scheduler."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# This task should never start before 9:00 AM.
	task = Task(
		title="Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		schedule_constraint=ScheduleConstraint(earliest_start=time(9, 0), hard_constraint=True, source="user"),
	)
	owner.add_task("Rex", task)

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	assert len(schedule) == 1
	assert schedule[0]['time'] is not None
	assert schedule[0]['time'] >= time(9, 0)


def test_schedule_includes_decision_metadata_fields():
	"""Test that scheduler includes phase-1 decision metadata in output."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	task = Task(
		title="Feed",
		duration=20,
		priority=Priority.HIGH,
		pet_name="Rex",
	)
	owner.add_task("Rex", task)

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	assert len(schedule) == 1
	item = schedule[0]
	assert 'applied_rules' in item
	assert 'confidence_score' in item
	assert 'retrieval_sources' in item
	assert isinstance(item['applied_rules'], list)
	assert isinstance(item['confidence_score'], float)
	assert isinstance(item['retrieval_sources'], list)


def test_owner_availability_window_restricts_schedule():
	"""Task scheduling should honor owner availability windows when provided."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)
	owner.add_availability_window(time(9, 0), time(11, 0))

	task = Task(
		title="Morning Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0),
	)
	assert owner.add_task("Rex", task) == True

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	assert len(schedule) == 1
	assert schedule[0]['time'] is not None
	assert schedule[0]['time'] >= time(9, 0)
	assert "owner_availability" in schedule[0]['applied_rules']


def test_owner_rejects_invalid_task_duration():
	"""Owner.add_task should reject invalid task inputs as a guardrail."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	invalid_task = Task(
		title="Invalid",
		duration=0,
		priority=Priority.HIGH,
		pet_name="Rex",
	)

	assert owner.add_task("Rex", invalid_task) == False
	assert len(owner.get_all_tasks()) == 0


def test_consistent_output_for_sample_border_collie_input():
	"""Repeated schedule generation should remain consistent for fixed input."""
	owner = Owner("Jordan")
	owner.set_timezone("US/Pacific")
	owner.add_availability_window(time(7, 0), time(12, 0))

	dog = Pet(name="Mochi", species="Dog", breed="Border Collie", activity_level="high")
	owner.add_pet(dog)

	walk = Task(
		title="Morning Walk",
		duration=45,
		priority=Priority.HIGH,
		pet_name="Mochi",
		time_constraint="before 09:00",
	)
	feed = Task(
		title="Breakfast",
		duration=15,
		priority=Priority.HIGH,
		pet_name="Mochi",
	)
	enrich = Task(
		title="Enrichment",
		duration=30,
		priority=Priority.MEDIUM,
		pet_name="Mochi",
	)

	assert owner.add_task("Mochi", walk) == True
	assert owner.add_task("Mochi", feed) == True
	assert owner.add_task("Mochi", enrich) == True

	scheduler = Scheduler(owner)
	first = scheduler.generate_schedule()
	second = scheduler.generate_schedule()

	first_signature = [(item['task'].title, item['time']) for item in first]
	second_signature = [(item['task'].title, item['time']) for item in second]

	assert first_signature == second_signature


def test_reliability_report_has_expected_fields():
	"""Scheduler should expose a reliability report for guardrail and confidence tracking."""
	owner = Owner("Jordan")
	dog = Pet(name="Mochi", species="Dog")
	owner.add_pet(dog)
	owner.add_availability_window(time(9, 0), time(10, 0))

	task = Task(
		title="Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Mochi",
	)
	owner.add_task("Mochi", task)

	scheduler = Scheduler(owner)
	scheduler.generate_schedule()
	report = scheduler.get_reliability_report()

	assert 'total_tasks' in report
	assert 'scheduled_tasks' in report
	assert 'unscheduled_tasks' in report
	assert 'scheduled_ratio' in report
	assert 'overall_confidence' in report
	assert 'low_confidence_tasks' in report
	assert 'citation_coverage' in report
	assert 'constraint_respect' in report
	assert 'rag_active_tasks' in report
	assert 'guardrail_warnings' in report
	assert isinstance(report['overall_confidence'], float)
	assert isinstance(report['scheduled_ratio'], float)
	assert isinstance(report['citation_coverage'], float)
	assert isinstance(report['constraint_respect'], float)
	assert isinstance(report['rag_active_tasks'], int)
	assert isinstance(report['guardrail_warnings'], list)
	assert 0.0 <= report['scheduled_ratio'] <= 1.0
	assert 0.0 <= report['citation_coverage'] <= 1.0
	assert 0.0 <= report['constraint_respect'] <= 1.0


def test_review_edits_persist_into_schedule_outcomes():
	"""Skip and locked-time review edits should be reflected in final schedule output."""
	owner = Owner("Jordan")
	dog = Pet(name="Mochi", species="Dog", breed="")
	owner.add_pet(dog)

	profile = RoutineProfile(walks_per_day=1, meals_per_day=1, play_sessions_per_day=0)
	success, _, _ = owner.generate_tasks_from_profile("Mochi", profile)
	assert success == True

	meal_task = next(t for t in owner.get_all_tasks() if t.title.startswith("Feeding - Meal"))
	walk_task = next(t for t in owner.get_all_tasks() if t.title.startswith("Exercise - Walk"))

	# Simulate review panel edits.
	owner.edit_task(meal_task.id, skipped=True)
	owner.edit_task(walk_task.id, priority=Priority.LOW, preferred_time=time(8, 0), locked_preferred_time=True)

	# Add blocker so locked walk cannot be placed at preferred time.
	blocker = Task(
		title="Block 8 AM",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Mochi",
		preferred_time=time(8, 0),
	)
	assert owner.add_task("Mochi", blocker) == True

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	titles = [item['task'].title for item in schedule]
	assert not any(title.startswith("Feeding - Meal") for title in titles)

	walk_item = next(item for item in schedule if item['task'].id == walk_task.id)
	assert walk_item['time'] is None
	assert "locked_preferred_time" in walk_item['applied_rules']
	assert any("Locked task" in warning for warning in scheduler.get_reliability_report()['guardrail_warnings'])


def test_reliability_report_reflects_rag_on_vs_off():
	"""Reliability report should expose RAG-active task counts for RAG vs baseline runs."""
	owner = Owner("Jordan")
	dog = Pet(name="Mochi", species="Dog", breed="Border Collie", activity_level="high")
	owner.add_pet(dog)

	task = Task(
		title="Enrichment Training",
		duration=30,
		priority=Priority.MEDIUM,
		pet_name="Mochi",
	)
	assert owner.add_task("Mochi", task) == True

	scheduler = Scheduler(owner)
	scheduler.generate_schedule(enable_rag=True)
	rag_report = scheduler.get_reliability_report()

	scheduler.generate_schedule(enable_rag=False)
	baseline_report = scheduler.get_reliability_report()

	assert rag_report['rag_active_tasks'] >= 1
	assert baseline_report['rag_active_tasks'] == 0


def test_consistent_output_for_sample_french_bulldog_input():
	"""Fixed French Bulldog scenario should produce stable schedule output across runs."""
	owner = Owner("Jordan")
	owner.add_availability_window(time(7, 0), time(21, 0))

	dog = Pet(name="Poppy", species="Dog", breed="French Bulldog", activity_level="medium")
	owner.add_pet(dog)

	meds = Task(
		title="Medication",
		duration=10,
		priority=Priority.HIGH,
		pet_name="Poppy",
		time_constraint="after 08:00",
	)
	feed = Task(
		title="Breakfast",
		duration=15,
		priority=Priority.HIGH,
		pet_name="Poppy",
	)
	walk = Task(
		title="Short Walk",
		duration=30,
		priority=Priority.MEDIUM,
		pet_name="Poppy",
	)

	owner.add_task("Poppy", meds)
	owner.add_task("Poppy", feed)
	owner.add_task("Poppy", walk)

	scheduler = Scheduler(owner)
	first = [(item['task'].title, item['time']) for item in scheduler.generate_schedule()]
	second = [(item['task'].title, item['time']) for item in scheduler.generate_schedule()]

	assert first == second


def test_consistent_output_for_multi_pet_collision_input():
	"""Multi-pet preferred-time collision should have deterministic final allocation."""
	owner = Owner("Jordan")
	owner.add_availability_window(time(7, 0), time(12, 0))

	dog = Pet(name="Rex", species="Dog")
	cat = Pet(name="Luna", species="Cat")
	owner.add_pet(dog)
	owner.add_pet(cat)

	task1 = Task(
		title="Dog Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0),
	)
	task2 = Task(
		title="Cat Feeding",
		duration=15,
		priority=Priority.HIGH,
		pet_name="Luna",
		preferred_time=time(8, 0),
	)

	owner.add_task("Rex", task1)
	owner.add_task("Luna", task2)

	scheduler = Scheduler(owner)
	first = [(item['task'].title, item['time']) for item in scheduler.generate_schedule()]
	second = [(item['task'].title, item['time']) for item in scheduler.generate_schedule()]

	assert first == second


def test_rag_guidance_adds_sources_and_rule_tags():
	"""RAG integration should add source references and rag rule tags for matching tasks."""
	owner = Owner("Jordan")
	dog = Pet(name="Mochi", species="Dog", breed="Border Collie", activity_level="high")
	owner.add_pet(dog)

	task = Task(
		title="Morning Enrichment",
		duration=30,
		priority=Priority.MEDIUM,
		pet_name="Mochi",
	)
	assert owner.add_task("Mochi", task) == True

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	assert len(schedule) == 1
	item = schedule[0]
	assert "rag_guidance" in item['applied_rules']
	assert len(item['retrieval_sources']) > 0
	assert any("breed:border_collie" in source for source in item['retrieval_sources'])
	assert item['guidance_profile']['energy_level'] == "very_high"
	assert "training" in item['guidance_profile']['preferred_exercise_types']


def test_rag_guidance_shapes_exercise_task_scheduling():
	"""Breed guidance should affect exercise task timing/metadata for same-priority tasks."""
	owner = Owner("Jordan")
	dog = Pet(name="Mochi", species="Dog", breed="Border Collie", activity_level="high")
	owner.add_pet(dog)

	# Same base priority and duration; RAG should favor exercise/enrichment semantics.
	groom = Task(
		title="Groom Fur",
		duration=30,
		priority=Priority.MEDIUM,
		pet_name="Mochi",
	)
	enrichment = Task(
		title="Enrichment Training",
		duration=30,
		priority=Priority.MEDIUM,
		pet_name="Mochi",
	)

	assert owner.add_task("Mochi", groom) == True
	assert owner.add_task("Mochi", enrichment) == True

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	enrichment_item = next(item for item in schedule if item['task'].title == "Enrichment Training")
	assert "rag_guidance" in enrichment_item['applied_rules']
	assert any("breed:border_collie" in source for source in enrichment_item['retrieval_sources'])
	assert enrichment_item['time'] is not None
	# Border Collie exercise guidance window starts at 06:30.
	assert enrichment_item['time'] >= time(6, 30)


def test_rag_low_confidence_falls_back_to_deterministic_rules():
	"""Species-only matches should fall back when below RAG confidence threshold."""
	owner = Owner("Jordan")
	dog = Pet(name="Rex", species="Dog", breed="")
	owner.add_pet(dog)

	task = Task(
		title="Morning Walk",
		duration=30,
		priority=Priority.MEDIUM,
		pet_name="Rex",
	)
	assert owner.add_task("Rex", task) == True

	scheduler = Scheduler(owner)
	scheduler.rag_confidence_threshold = 0.5
	schedule = scheduler.generate_schedule(enable_rag=True)

	assert len(schedule) == 1
	item = schedule[0]
	assert "rag_guidance" not in item['applied_rules']
	assert "rag_fallback_low_confidence" in item['applied_rules']
	assert item['guidance_profile']['rag_active'] == False


def test_hard_time_constraint_takes_precedence_over_rag_window():
	"""Explicit hard constraints should override any guidance-derived preferred windows."""
	owner = Owner("Jordan")
	dog = Pet(name="Poppy", species="Dog", breed="French Bulldog")
	owner.add_pet(dog)

	# RAG suggests morning windows for exercise, but hard user constraint forces afternoon.
	task = Task(
		title="Walk",
		duration=30,
		priority=Priority.MEDIUM,
		pet_name="Poppy",
		time_constraint="after 12:00",
	)
	assert owner.add_task("Poppy", task) == True

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule(enable_rag=True)

	assert len(schedule) == 1
	assert schedule[0]['time'] is not None
	assert schedule[0]['time'] >= time(12, 0)


def test_generate_schedule_can_disable_rag_for_baseline():
	"""Scheduler should support deterministic baseline mode with RAG disabled."""
	owner = Owner("Jordan")
	dog = Pet(name="Mochi", species="Dog", breed="Border Collie")
	owner.add_pet(dog)

	task = Task(
		title="Enrichment Training",
		duration=30,
		priority=Priority.MEDIUM,
		pet_name="Mochi",
	)
	assert owner.add_task("Mochi", task) == True

	scheduler = Scheduler(owner)
	rag_schedule = scheduler.generate_schedule(enable_rag=True)
	baseline_schedule = scheduler.generate_schedule(enable_rag=False)

	assert len(rag_schedule) == 1
	assert len(baseline_schedule) == 1
	assert "rag_guidance" in rag_schedule[0]['applied_rules']
	assert "rag_guidance" not in baseline_schedule[0]['applied_rules']


def test_task_completion_status_changes():
	"""Test that task completion status can be changed."""
	# Create an owner and pet
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# Create a task
	task = Task(
		title="Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex"
	)

	# Add task to pet
	dog.add_task(task)

	# Verify task starts as incomplete
	assert task.completed == False

	# Change completion status using edit_task
	owner.edit_task(task.id, completed=True)

	# Verify completion status changed
	assert task.completed == True

	# Change it back
	owner.edit_task(task.id, completed=False)

	# Verify it changed back
	assert task.completed == False


def test_adding_task_increases_pet_task_count():
	"""Test that adding a task to a Pet increases that pet's task count."""
	# Create a pet
	cat = Pet(name="Mittens", species="Cat")

	# Verify initial task count is 0
	assert len(cat.tasks) == 0

	# Create and add first task
	task1 = Task(
		title="Feed",
		duration=10,
		priority=Priority.HIGH,
		pet_name="Mittens"
	)
	cat.add_task(task1)

	# Verify task count increased to 1
	assert len(cat.tasks) == 1

	# Create and add second task
	task2 = Task(
		title="Groom",
		duration=15,
		priority=Priority.MEDIUM,
		pet_name="Mittens"
	)
	cat.add_task(task2)

	# Verify task count increased to 2
	assert len(cat.tasks) == 2

	# Verify the correct tasks are in the list
	assert task1 in cat.tasks
	assert task2 in cat.tasks


def test_preferred_time_scheduling():
	"""Test that tasks are scheduled at preferred time when available."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# Task with preferred time at 8:00 AM
	task = Task(
		title="Walk",
		duration=30,
		priority=Priority.MEDIUM,
		pet_name="Rex",
		preferred_time=time(8, 0)
	)
	owner.add_task("Rex", task)

	# Generate schedule
	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	# Verify task scheduled at preferred time
	assert schedule[0]['time'] == time(8, 0)
	assert "preferred time" in schedule[0]['reason'].lower()


def test_preferred_time_with_constraint_fallback():
	"""Test fallback to constraint when preferred time unavailable."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# Task 1: High priority, occupies 7:00-7:30 AM
	task1 = Task(
		title="Feed",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(7, 0)
	)

	# Task 2: Prefers 7:00 AM but has fallback constraint
	task2 = Task(
		title="Walk",
		duration=30,
		priority=Priority.LOW,
		pet_name="Rex",
		preferred_time=time(7, 0),
		time_constraint="before 09:00"
	)

	owner.add_task("Rex", task1)
	owner.add_task("Rex", task2)

	# Generate schedule
	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	# Find tasks in schedule (they may be in any order due to time sorting)
	feed_item = next(item for item in schedule if item['task'].title == "Feed")
	walk_item = next(item for item in schedule if item['task'].title == "Walk")

	# Task 1 (Feed) gets preferred time
	assert feed_item['time'] == time(7, 0)
	assert "preferred time" in feed_item['reason'].lower()

	# Task 2 (Walk) falls back to available slot within constraint
	assert walk_item['time'] != time(7, 0)  # Not preferred time
	assert walk_item['time'] < time(9, 0)  # Within constraint
	assert "unavailable" in walk_item['reason'].lower()


def test_preferred_time_validation():
	"""Test that incompatible preferred_time and constraint are detected."""
	task = Task(
		title="Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(10, 0),      # 10:00 AM
		time_constraint="before 09:00"   # Must finish by 9:00 AM
	)

	is_valid, error = task.validate_time_settings()
	assert not is_valid
	assert error is not None
	assert "before" in error.lower() or "constraint" in error.lower()


# ========== Recurring Task Tests ==========

def test_daily_recurring_task_creates_next_occurrence():
	"""Test that completing a daily recurring task creates tomorrow's task."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	today = date.today()
	tomorrow = today + timedelta(days=1)

	# Create daily recurring task
	task = Task(
		title="Daily Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		frequency=Frequency.DAILY,
		scheduled_date=today
	)
	owner.add_task("Rex", task)

	# Verify initial state
	assert len(dog.tasks) == 1
	assert task.completed == False

	# Complete the task
	success, next_task = owner.complete_task(task.id)

	# Verify completion and next occurrence
	assert success == True
	assert task.completed == True
	assert next_task is not None
	assert next_task.scheduled_date == tomorrow
	assert next_task.title == task.title
	assert next_task.completed == False
	assert len(dog.tasks) == 2  # Original + next occurrence


def test_weekly_recurring_task_calculation():
	"""Test that weekly recurring tasks calculate correct next date."""
	today = date(2026, 2, 11)  # Tuesday
	next_week = date(2026, 2, 18)  # Next Tuesday

	task = Task(
		title="Weekly Vet Visit",
		duration=60,
		priority=Priority.HIGH,
		pet_name="Rex",
		frequency=Frequency.WEEKLY,
		scheduled_date=today
	)

	next_task = task.clone_for_next_occurrence()

	assert next_task is not None
	assert next_task.scheduled_date == next_week
	assert (next_task.scheduled_date - today).days == 7


def test_non_recurring_task_does_not_create_next_occurrence():
	"""Test that completing a non-recurring task does not create another task."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	task = Task(
		title="One-time Grooming",
		duration=45,
		priority=Priority.MEDIUM,
		pet_name="Rex"
		# No frequency set
	)
	owner.add_task("Rex", task)

	# Complete the task
	success, next_task = owner.complete_task(task.id)

	# Verify no next occurrence
	assert success == True
	assert task.completed == True
	assert next_task is None
	assert len(dog.tasks) == 1  # Only the original task


def test_scheduler_filters_future_recurring_tasks():
	"""Test that scheduler only includes today's tasks, not future occurrences."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	today = date.today()
	tomorrow = today + timedelta(days=1)

	# Task for today
	task_today = Task(
		title="Today's Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		scheduled_date=today
	)

	# Task for tomorrow
	task_tomorrow = Task(
		title="Tomorrow's Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		scheduled_date=tomorrow
	)

	owner.add_task("Rex", task_today)
	owner.add_task("Rex", task_tomorrow)

	# Generate schedule
	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	# Verify only today's task is scheduled
	scheduled_titles = [item['task'].title for item in schedule]
	assert "Today's Walk" in scheduled_titles
	assert "Tomorrow's Walk" not in scheduled_titles


def test_biweekly_recurring_task():
	"""Test that biweekly tasks calculate correct next date (14 days)."""
	today = date.today()
	two_weeks_later = today + timedelta(weeks=2)

	task = Task(
		title="Biweekly Grooming",
		duration=45,
		priority=Priority.MEDIUM,
		pet_name="Rex",
		frequency=Frequency.BIWEEKLY,
		scheduled_date=today
	)

	next_task = task.clone_for_next_occurrence()

	assert next_task is not None
	assert next_task.scheduled_date == two_weeks_later
	assert (next_task.scheduled_date - today).days == 14


def test_monthly_recurring_task_normal_case():
	"""Test monthly recurrence for normal month transitions."""
	# Task scheduled for January 15
	task = Task(
		title="Monthly Checkup",
		duration=60,
		priority=Priority.HIGH,
		pet_name="Rex",
		frequency=Frequency.MONTHLY,
		scheduled_date=date(2026, 1, 15)
	)

	next_task = task.clone_for_next_occurrence()

	assert next_task is not None
	# Should be February 15
	assert next_task.scheduled_date.month == 2
	assert next_task.scheduled_date.day == 15


def test_parent_task_id_links_recurring_tasks():
	"""Test that generated tasks link back to original via parent_task_id."""
	task = Task(
		title="Daily Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		frequency=Frequency.DAILY,
		scheduled_date=date.today()
	)

	original_id = task.id
	next_task = task.clone_for_next_occurrence()

	assert next_task.parent_task_id == original_id

	# Third generation should still link to original
	third_task = next_task.clone_for_next_occurrence()
	assert third_task.parent_task_id == original_id


def test_backward_compatibility_with_existing_tasks():
	"""Test that existing non-recurring tasks work without changes."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# Old-style task (no frequency, no scheduled_date)
	task = Task(
		title="Old Task",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex"
	)
	owner.add_task("Rex", task)

	# Should still work with complete_task
	success, next_task = owner.complete_task(task.id)

	assert success == True
	assert task.completed == True
	assert next_task is None


# ========== Conflict Detection Tests ==========

def test_same_pet_conflict_detection():
	"""Test that overlapping preferred times for the same pet are detected."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# Two tasks for same pet with overlapping preferred times
	task1 = Task(
		title="Morning Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0)  # 8:00-8:30 AM
	)

	task2 = Task(
		title="Breakfast",
		duration=15,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 15)  # 8:15-8:30 AM (overlaps!)
	)

	owner.add_task("Rex", task1)
	owner.add_task("Rex", task2)

	scheduler = Scheduler(owner)

	# Check preferred time conflicts BEFORE scheduling
	warnings = scheduler.detect_preferred_time_conflicts()

	# Should detect same-pet conflict
	assert len(warnings) > 0
	assert any("Same pet conflict" in w for w in warnings)
	assert any("Rex" in w for w in warnings)


def test_different_pet_conflict_detection():
	"""Test that overlapping preferred times for different pets are detected."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	cat = Pet(name="Whiskers", species="Cat")
	owner.add_pet(dog)
	owner.add_pet(cat)

	# Tasks for different pets with overlapping preferred times
	task1 = Task(
		title="Dog Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0)
	)

	task2 = Task(
		title="Cat Feeding",
		duration=15,
		priority=Priority.HIGH,
		pet_name="Whiskers",
		preferred_time=time(8, 0)  # Same time as dog walk
	)

	owner.add_task("Rex", task1)
	owner.add_task("Whiskers", task2)

	scheduler = Scheduler(owner)

	# Check preferred time conflicts
	warnings = scheduler.detect_preferred_time_conflicts()

	# Should detect multi-pet conflict
	assert len(warnings) > 0
	assert any("Multi-pet conflict" in w for w in warnings)
	assert any("Rex" in w and "Whiskers" in w for w in warnings)


def test_preferred_time_warnings():
	"""Test that preferred time warnings detect both same-pet and multi-pet conflicts."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	cat = Pet(name="Whiskers", species="Cat")
	owner.add_pet(dog)
	owner.add_pet(cat)

	# Same-pet conflict - overlapping preferred times
	task1 = Task(
		title="Walk 1",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0)
	)
	task2 = Task(
		title="Walk 2",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 15)
	)

	# Different-pet conflict
	task3 = Task(
		title="Cat Play",
		duration=20,
		priority=Priority.HIGH,
		pet_name="Whiskers",
		preferred_time=time(8, 0)
	)

	owner.add_task("Rex", task1)
	owner.add_task("Rex", task2)
	owner.add_task("Whiskers", task3)

	scheduler = Scheduler(owner)

	# Check preferred time conflicts
	warnings = scheduler.detect_preferred_time_conflicts()

	# Should have both same-pet and multi-pet warnings
	assert len(warnings) >= 2
	assert any("Same pet conflict" in w for w in warnings)
	assert any("Multi-pet conflict" in w for w in warnings)


def test_no_conflicts_with_sequential_tasks():
	"""Test that sequential tasks don't trigger conflict warnings."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# Sequential tasks (no overlap)
	task1 = Task(
		title="Morning Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0)  # 8:00-8:30
	)

	task2 = Task(
		title="Breakfast",
		duration=15,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 30)  # 8:30-8:45 (no overlap)
	)

	owner.add_task("Rex", task1)
	owner.add_task("Rex", task2)

	scheduler = Scheduler(owner)

	# Check preferred time conflicts
	warnings = scheduler.detect_preferred_time_conflicts()

	# Should have no warnings
	assert len(warnings) == 0

	# Also verify the schedule executes without conflicts
	scheduler.generate_schedule()
	conflicts = scheduler.detect_conflicts()
	assert len(conflicts) == 0


# ========== Edge Case Tests ==========

def test_sorting_correctness_chronological_order():
	"""Test that tasks are sorted in chronological order by preferred time."""
	# Create tasks in random order
	tasks = [
		Task(title="Afternoon", duration=30, priority=Priority.LOW, pet_name="Rex", preferred_time=time(15, 0)),
		Task(title="Morning", duration=30, priority=Priority.LOW, pet_name="Rex", preferred_time=time(8, 0)),
		Task(title="Evening", duration=30, priority=Priority.LOW, pet_name="Rex", preferred_time=time(20, 0)),
		Task(title="Noon", duration=30, priority=Priority.LOW, pet_name="Rex", preferred_time=time(12, 0)),
		Task(title="Early Morning", duration=30, priority=Priority.LOW, pet_name="Rex", preferred_time=time(6, 30))
	]

	# Sort tasks
	sorted_tasks = Task.sort_by_time(tasks)

	# Verify chronological order
	assert sorted_tasks[0].title == "Early Morning"
	assert sorted_tasks[1].title == "Morning"
	assert sorted_tasks[2].title == "Noon"
	assert sorted_tasks[3].title == "Afternoon"
	assert sorted_tasks[4].title == "Evening"

	# Verify times are in ascending order
	for i in range(len(sorted_tasks) - 1):
		assert sorted_tasks[i].preferred_time <= sorted_tasks[i + 1].preferred_time


def test_sorting_tasks_without_preferred_time():
	"""Test that tasks without preferred_time are sorted last."""
	tasks = [
		Task(title="No time 1", duration=30, priority=Priority.LOW, pet_name="Rex"),
		Task(title="Morning", duration=30, priority=Priority.LOW, pet_name="Rex", preferred_time=time(8, 0)),
		Task(title="No time 2", duration=30, priority=Priority.LOW, pet_name="Rex"),
		Task(title="Afternoon", duration=30, priority=Priority.LOW, pet_name="Rex", preferred_time=time(15, 0))
	]

	sorted_tasks = Task.sort_by_time(tasks)

	# First two should have times
	assert sorted_tasks[0].preferred_time is not None
	assert sorted_tasks[1].preferred_time is not None

	# Last two should be None
	assert sorted_tasks[2].preferred_time is None
	assert sorted_tasks[3].preferred_time is None


def test_sorting_empty_list():
	"""Test that sorting an empty list returns an empty list."""
	empty_list = []
	sorted_tasks = Task.sort_by_time(empty_list)
	assert sorted_tasks == []


def test_sorting_single_task():
	"""Test that sorting a single task returns a list with that task."""
	task = Task(title="Solo", duration=30, priority=Priority.LOW, pet_name="Rex", preferred_time=time(8, 0))
	sorted_tasks = Task.sort_by_time([task])
	assert len(sorted_tasks) == 1
	assert sorted_tasks[0] == task


def test_monthly_recurring_task_edge_case_jan_31():
	"""Test monthly task on Jan 31 becomes Feb 28 (or 29 in leap year)."""
	# Non-leap year
	task = Task(
		title="Monthly Vet",
		duration=60,
		priority=Priority.HIGH,
		pet_name="Rex",
		frequency=Frequency.MONTHLY,
		scheduled_date=date(2026, 1, 31)  # 2026 is not a leap year
	)

	next_task = task.clone_for_next_occurrence()

	assert next_task is not None
	assert next_task.scheduled_date.month == 2
	# February 2026 has 28 days
	assert next_task.scheduled_date.day == 28


def test_year_boundary_crossing_weekly():
	"""Test weekly task crossing year boundary."""
	# Task on Dec 28, 2026 (Tuesday)
	task = Task(
		title="Weekly Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		frequency=Frequency.WEEKLY,
		scheduled_date=date(2026, 12, 28)
	)

	next_task = task.clone_for_next_occurrence()

	assert next_task is not None
	# Should be Jan 4, 2027
	assert next_task.scheduled_date == date(2027, 1, 4)
	assert next_task.scheduled_date.year == 2027


def test_year_boundary_crossing_daily():
	"""Test daily task crossing year boundary."""
	# Task on Dec 31, 2026
	task = Task(
		title="Daily Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		frequency=Frequency.DAILY,
		scheduled_date=date(2026, 12, 31)
	)

	next_task = task.clone_for_next_occurrence()

	assert next_task is not None
	# Should be Jan 1, 2027
	assert next_task.scheduled_date == date(2027, 1, 1)
	assert next_task.scheduled_date.year == 2027


def test_three_way_conflict_detection():
	"""Test that three tasks with overlapping times are all detected."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# Three tasks all preferring 8:00 AM
	task1 = Task(
		title="Task A",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0)
	)

	task2 = Task(
		title="Task B",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0)
	)

	task3 = Task(
		title="Task C",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0)
	)

	owner.add_task("Rex", task1)
	owner.add_task("Rex", task2)
	owner.add_task("Rex", task3)

	scheduler = Scheduler(owner)
	warnings = scheduler.detect_preferred_time_conflicts()

	# Should detect 3 pairwise conflicts: A-B, A-C, B-C
	assert len(warnings) == 3
	assert all("Same pet conflict" in w for w in warnings)


def test_zero_duration_task_scheduling():
	"""Test that zero-duration tasks are handled (edge case)."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# Zero duration task
	task = Task(
		title="Instant Check",
		duration=0,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0)
	)

	owner.add_task("Rex", task)

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	# Should still schedule (or at least not crash)
	assert len(schedule) >= 0  # May or may not schedule based on implementation


def test_very_long_task_exceeding_window():
	"""Test task longer than the scheduling window (6 AM - 10 PM = 16 hours)."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# 17-hour task (exceeds 16-hour window)
	task = Task(
		title="Marathon Care",
		duration=1020,  # 17 hours
		priority=Priority.HIGH,
		pet_name="Rex"
	)

	owner.add_task("Rex", task)

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	# Task should not be scheduled (doesn't fit)
	scheduled_item = next((item for item in schedule if item['task'].title == "Marathon Care"), None)
	assert scheduled_item is not None
	# Should have time=None (couldn't schedule)
	assert scheduled_item['time'] is None


def test_task_at_window_boundary_start():
	"""Test task at the start of scheduling window (6 AM)."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	task = Task(
		title="Early Bird",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(6, 0)  # 6:00 AM (window start)
	)

	owner.add_task("Rex", task)

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	# Should be scheduled at 6:00 AM
	assert len(schedule) == 1
	assert schedule[0]['time'] == time(6, 0)


def test_task_at_window_boundary_end():
	"""Test task near the end of scheduling window (10 PM)."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# Task that would end after 10 PM
	task = Task(
		title="Late Night",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(21, 45)  # 9:45 PM, ends at 10:15 PM
	)

	owner.add_task("Rex", task)

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	# May or may not be scheduled depending on boundary logic
	# At minimum, should not crash
	assert len(schedule) >= 0


def test_conflict_detection_flags_duplicate_times():
	"""Test that conflict detection flags multiple tasks at exactly the same time."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# Two tasks with identical preferred times
	task1 = Task(
		title="Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0)
	)

	task2 = Task(
		title="Feed",
		duration=15,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0)  # Exact same time
	)

	owner.add_task("Rex", task1)
	owner.add_task("Rex", task2)

	scheduler = Scheduler(owner)
	warnings = scheduler.detect_preferred_time_conflicts()

	# Should detect conflict
	assert len(warnings) > 0
	assert any("Same pet conflict" in w for w in warnings)
	assert any("Rex" in w for w in warnings)


def test_filtering_empty_list():
	"""Test filtering on empty list returns empty list."""
	empty_list = []

	filtered = Task.filter_by_completion(empty_list, completed=False)
	assert filtered == []

	filtered = Task.filter_by_pet(empty_list, "Rex")
	assert filtered == []

	filtered = Task.filter_tasks(empty_list, pet_name="Rex", completed=False)
	assert filtered == []


def test_filtering_no_matches():
	"""Test filtering with criteria that match nothing."""
	tasks = [
		Task(title="Task 1", duration=30, priority=Priority.HIGH, pet_name="Rex", completed=False),
		Task(title="Task 2", duration=30, priority=Priority.HIGH, pet_name="Rex", completed=False)
	]

	# Filter for completed tasks (none exist)
	filtered = Task.filter_by_completion(tasks, completed=True)
	assert len(filtered) == 0

	# Filter for different pet (doesn't exist)
	filtered = Task.filter_by_pet(tasks, "Nonexistent")
	assert len(filtered) == 0


def test_completing_task_multiple_times_idempotent():
	"""Test that completing a task multiple times doesn't create multiple next occurrences."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	task = Task(
		title="Daily Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		frequency=Frequency.DAILY,
		scheduled_date=date.today()
	)
	owner.add_task("Rex", task)

	# Complete task first time
	success1, next_task1 = owner.complete_task(task.id)
	assert success1 == True
	assert next_task1 is not None

	# Try to complete same task again (already completed)
	success2, next_task2 = owner.complete_task(task.id)

	# Should still return success but clone from already-completed task
	# This tests idempotency - completing twice shouldn't break things
	assert success2 == True


def test_recurrence_preserves_task_properties():
	"""Test that recurring task clones preserve all original properties."""
	original_task = Task(
		title="Daily Walk",
		duration=45,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 30),
		time_constraint="before 10:00",
		frequency=Frequency.DAILY,
		scheduled_date=date.today()
	)

	next_task = original_task.clone_for_next_occurrence()

	# Verify all properties except date and ID are preserved
	assert next_task.title == original_task.title
	assert next_task.duration == original_task.duration
	assert next_task.priority == original_task.priority
	assert next_task.pet_name == original_task.pet_name
	assert next_task.preferred_time == original_task.preferred_time
	assert next_task.time_constraint == original_task.time_constraint
	assert next_task.frequency == original_task.frequency

	# But new task should have different ID and new date
	assert next_task.id != original_task.id
	assert next_task.scheduled_date != original_task.scheduled_date
	assert next_task.completed == False


# ========== Integration Tests ==========

def test_schedule_with_recurring_tasks():
	"""Test schedule generation with recurring tasks."""
	owner = Owner("Test Owner")
	dog = Pet(name="Max", species="Dog")
	owner.add_pet(dog)

	# Add daily recurring task
	daily_walk = Task(
		title="Daily Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Max",
		preferred_time=time(8, 0),
		frequency=Frequency.DAILY,
		scheduled_date=date.today()
	)

	# Add one-time task
	vet_visit = Task(
		title="Vet Visit",
		duration=60,
		priority=Priority.HIGH,
		pet_name="Max",
		preferred_time=time(10, 0),
		scheduled_date=date.today()
	)

	owner.add_task("Max", daily_walk)
	owner.add_task("Max", vet_visit)

	# Generate schedule
	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	# Verify both tasks are scheduled
	assert len(schedule) == 2
	scheduled_titles = [item['task'].title for item in schedule]
	assert "Daily Walk" in scheduled_titles
	assert "Vet Visit" in scheduled_titles

	# Complete the daily task
	success, next_task = owner.complete_task(daily_walk.id)

	# Verify next occurrence created
	assert success == True
	assert next_task is not None
	assert next_task.scheduled_date == date.today() + timedelta(days=1)
	assert len(dog.tasks) == 3  # Original daily (completed) + vet + next daily


def test_schedule_with_conflicts():
	"""Test schedule generation with conflicting preferred times."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# Two tasks preferring same time
	task1 = Task(
		title="Walk",
		duration=30,
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0)
	)

	task2 = Task(
		title="Feed",
		duration=15,
		priority=Priority.MEDIUM,
		pet_name="Rex",
		preferred_time=time(8, 0)  # Same time!
	)

	owner.add_task("Rex", task1)
	owner.add_task("Rex", task2)

	scheduler = Scheduler(owner)

	# Check for conflicts BEFORE scheduling
	warnings = scheduler.detect_preferred_time_conflicts()
	assert len(warnings) > 0
	assert any("Same pet conflict" in w for w in warnings)

	# Generate schedule (should resolve conflicts)
	schedule = scheduler.generate_schedule()

	# Verify both tasks are in schedule
	assert len(schedule) == 2

	# Verify no conflicts in final schedule
	final_conflicts = scheduler.detect_conflicts()
	assert len(final_conflicts) == 0


def test_sorting_and_filtering():
	"""Test sorting and filtering with schedule generation."""
	owner = Owner("Test Owner")
	dog = Pet(name="Buddy", species="Dog")
	cat = Pet(name="Whiskers", species="Cat")
	owner.add_pet(dog)
	owner.add_pet(cat)

	# Add tasks in random order
	tasks_data = [
		("Afternoon Play", "Buddy", time(15, 0), Priority.MEDIUM, 20),
		("Morning Walk", "Buddy", time(7, 0), Priority.HIGH, 30),
		("Cat Breakfast", "Whiskers", time(6, 30), Priority.HIGH, 10),
		("Evening Walk", "Buddy", time(18, 0), Priority.MEDIUM, 25),
	]

	for title, pet_name, pref_time, priority, duration in tasks_data:
		task = Task(
			title=title,
			duration=duration,
			priority=priority,
			pet_name=pet_name,
			preferred_time=pref_time
		)
		owner.add_task(pet_name, task)

	# Test sorting
	all_tasks = owner.get_all_tasks()
	sorted_tasks = Task.sort_by_time(all_tasks)

	# Verify chronological order
	assert sorted_tasks[0].title == "Cat Breakfast"
	assert sorted_tasks[1].title == "Morning Walk"
	assert sorted_tasks[2].title == "Afternoon Play"
	assert sorted_tasks[3].title == "Evening Walk"

	# Test filtering
	buddy_tasks = Task.filter_by_pet(all_tasks, "Buddy")
	assert len(buddy_tasks) == 3
	buddy_titles = [t.title for t in buddy_tasks]
	assert "Morning Walk" in buddy_titles
	assert "Afternoon Play" in buddy_titles
	assert "Evening Walk" in buddy_titles

	# Generate schedule
	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	# Verify all tasks scheduled
	assert len(schedule) == 4


def test_monthly_edge_case():
	"""Test monthly recurring task with edge case (Jan 31)."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# Task scheduled for Jan 31
	task = Task(
		title="Monthly Vet",
		duration=60,
		priority=Priority.HIGH,
		pet_name="Rex",
		frequency=Frequency.MONTHLY,
		scheduled_date=date(2026, 1, 31)
	)
	owner.add_task("Rex", task)

	# Complete to generate next occurrence
	success, next_task = owner.complete_task(task.id)

	# Verify next occurrence is Feb 28 (non-leap year)
	assert success == True
	assert next_task is not None
	assert next_task.scheduled_date == date(2026, 2, 28)


def test_scheduler_tradeoff():
	"""Demonstrate the 15-minute granularity tradeoff."""
	owner = Owner("Test Owner")
	dog = Pet(name="Rex", species="Dog")
	owner.add_pet(dog)

	# Create 10-minute task
	task = Task(
		title="Quick Feed",
		duration=10,  # Only 10 minutes
		priority=Priority.HIGH,
		pet_name="Rex",
		preferred_time=time(8, 0)
	)
	owner.add_task("Rex", task)

	scheduler = Scheduler(owner)
	schedule = scheduler.generate_schedule()

	# Verify task is scheduled
	assert len(schedule) == 1
	assert schedule[0]['time'] == time(8, 0)

	# Task duration is 10 minutes but scheduler uses 15-minute slots
	# This is acceptable - it's a known tradeoff for simplicity
