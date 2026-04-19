from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import time, date, timedelta
import uuid

from rag.guidance_service import BreedGuidanceService

class Priority(Enum):
	"""Priority levels for tasks, making comparison easier."""
	LOW = 1
	MEDIUM = 2
	HIGH = 3

class Frequency(Enum):
	"""Frequency options for recurring tasks."""
	DAILY = "daily"
	WEEKLY = "weekly"
	BIWEEKLY = "biweekly"
	MONTHLY = "monthly"


@dataclass
class ScheduleConstraint:
	"""Structured scheduling constraints for a task."""
	earliest_start: Optional[time] = None
	latest_end: Optional[time] = None
	hard_constraint: bool = True
	source: str = "user"


@dataclass
class RoutineProfile:
	"""High-level care preferences used to auto-generate daily tasks."""
	walks_per_day: int = 1
	meals_per_day: int = 2
	play_sessions_per_day: int = 1
	medication_times: List[time] = field(default_factory=list)
	grooming_sessions_per_week: int = 0
	walk_window_start: Optional[time] = time(7, 0)
	walk_window_end: Optional[time] = time(10, 0)
	meal_window_start: Optional[time] = time(7, 0)
	meal_window_end: Optional[time] = time(19, 0)
	play_window_start: Optional[time] = time(8, 0)
	play_window_end: Optional[time] = time(20, 0)

	def validate(self) -> tuple[bool, Optional[str]]:
		if self.walks_per_day < 0 or self.meals_per_day < 0 or self.play_sessions_per_day < 0:
			return False, "Walk, meal, and play frequencies cannot be negative."
		if self.grooming_sessions_per_week < 0:
			return False, "Grooming frequency cannot be negative."
		if self.walk_window_start and self.walk_window_end and self.walk_window_start >= self.walk_window_end:
			return False, "Walk window start must be earlier than walk window end."
		if self.meal_window_start and self.meal_window_end and self.meal_window_start >= self.meal_window_end:
			return False, "Meal window start must be earlier than meal window end."
		if self.play_window_start and self.play_window_end and self.play_window_start >= self.play_window_end:
			return False, "Play window start must be earlier than play window end."
		return True, None

@dataclass
class Pet:
	name: str
	species: str
	breed: str = ""
	age_years: Optional[float] = None
	activity_level: str = "medium"
	preferences: dict = field(default_factory=dict)
	restrictions: List[str] = field(default_factory=list)  # e.g., ["no_midday_walks", "medication_8am"]
	tasks: List[Task] = field(default_factory=list)  # Pet stores its own tasks

	def add_task(self, task: Task) -> None:
		"""Add a task to this pet's task list."""
		self.tasks.append(task)

	def get_task_by_id(self, task_id: str) -> Optional[Task]:
		"""Find a task by its ID."""
		for task in self.tasks:
			if task.id == task_id:
				return task
		return None

	def get_incomplete_tasks(self) -> List[Task]:
		"""Return all tasks that haven't been completed."""
		return [task for task in self.tasks if not task.completed]

	def get_tasks_by_priority(self, priority: Priority) -> List[Task]:
		"""Return all tasks with the specified priority."""
		return [task for task in self.tasks if task.priority == priority]

@dataclass
class Task:
	title: str
	duration: int  # in minutes
	priority: Priority
	pet_name: str  # Links task to specific pet - addresses missing Pet-Task relationship
	id: str = field(default_factory=lambda: str(uuid.uuid4()))  # Fixes task identification bottleneck
	is_recurring: bool = False
	preferred_time: Optional[time] = None  # User's preferred time for task
	time_constraint: Optional[str] = None  # e.g., "before 08:00", "after 18:00"
	schedule_constraint: ScheduleConstraint = field(default_factory=ScheduleConstraint)
	completed: bool = False  # Completion status
	frequency: Optional[Frequency] = None  # Recurrence pattern (None for non-recurring tasks)
	scheduled_date: Optional[date] = None  # The specific date this task is for
	parent_task_id: Optional[str] = None  # Links to the original recurring task template
	retrieval_sources: List[str] = field(default_factory=list)
	task_source: str = "manual"
	skipped: bool = False
	locked_preferred_time: bool = False

	def validate_basic_fields(self) -> tuple[bool, Optional[str]]:
		"""Validate required fields and basic bounds for safe scheduling."""
		if not self.title or not self.title.strip():
			return False, "Task title is required."
		if not self.pet_name or not self.pet_name.strip():
			return False, "Pet name is required."
		if self.duration <= 0:
			return False, "Task duration must be greater than 0 minutes."
		if self.schedule_constraint.earliest_start and self.schedule_constraint.latest_end:
			if self.schedule_constraint.earliest_start >= self.schedule_constraint.latest_end:
				return False, "Structured constraint earliest_start must be earlier than latest_end."
		return True, None

	@staticmethod
	def parse_preferred_time(time_str: str) -> Optional[time]:
		"""Parse time string (e.g., '08:00', '8:00 AM') to time object.

		Returns None if parsing fails.
		"""
		if not time_str:
			return None

		try:
			# Try 24-hour format (HH:MM)
			if ':' in time_str and ('AM' not in time_str.upper() and 'PM' not in time_str.upper()):
				hour, minute = map(int, time_str.strip().split(':'))
				return time(hour, minute)

			# Try 12-hour format (HH:MM AM/PM)
			from datetime import datetime
			parsed = datetime.strptime(time_str.strip(), '%I:%M %p')
			return parsed.time()
		except:
			return None

	def validate_time_settings(self) -> tuple[bool, Optional[str]]:
		"""Validate that preferred_time and time_constraint are compatible.

		Returns (is_valid, error_message).
		"""
		if not self.preferred_time:
			return True, None

		# Need to parse constraint - use a temporary scheduler instance
		# This is a bit awkward but avoids circular dependencies
		from datetime import datetime, timedelta

		earliest = self.schedule_constraint.earliest_start
		latest = self.schedule_constraint.latest_end

		if self.time_constraint and not earliest and not latest:
			constraint = self.time_constraint.lower().strip()
			if "before" in constraint:
				time_str = constraint.split("before")[1].strip()
				hour, minute = map(int, time_str.split(":"))
				latest = time(hour, minute)
			elif "after" in constraint:
				time_str = constraint.split("after")[1].strip()
				hour, minute = map(int, time_str.split(":"))
				earliest = time(hour, minute)

		if not earliest and not latest:
			return True, None

		# Check if preferred time satisfies constraint
		if earliest and self.preferred_time < earliest:
			return False, f"Preferred time {self.preferred_time.strftime('%I:%M %p')} is before constraint earliest time"

		if latest:
			# Check if task would finish by latest time
			preferred_dt = datetime.combine(datetime.today(), self.preferred_time)
			end_dt = preferred_dt + timedelta(minutes=self.duration)
			end_time = end_dt.time()

			if end_time > latest:
				return False, f"Task ending at {end_time.strftime('%I:%M %p')} exceeds constraint latest time"

		return True, None

	@staticmethod
	def sort_by_time(tasks: List['Task']) -> List['Task']:
		"""Sort tasks by their preferred_time in HH:MM format.

		Tasks without a preferred_time will be sorted last.

		Args:
			tasks: List of Task objects to sort

		Returns:
			New list of tasks sorted by preferred_time

		Example:
			sorted_tasks = Task.sort_by_time(my_tasks)
		"""
		return sorted(
			tasks,
			key=lambda task: task.preferred_time.strftime("%H:%M") if task.preferred_time else "99:99"
		)

	@staticmethod
	def filter_by_completion(tasks: List['Task'], completed: bool) -> List['Task']:
		"""Filter tasks by completion status.

		Args:
			tasks: List of Task objects to filter
			completed: True for completed tasks, False for incomplete tasks

		Returns:
			New list of tasks matching the completion status

		Example:
			incomplete_tasks = Task.filter_by_completion(my_tasks, completed=False)
		"""
		return [task for task in tasks if task.completed == completed]

	@staticmethod
	def filter_by_pet(tasks: List['Task'], pet_name: str) -> List['Task']:
		"""Filter tasks by pet name.

		Args:
			tasks: List of Task objects to filter
			pet_name: Name of the pet to filter by

		Returns:
			New list of tasks for the specified pet

		Example:
			mochi_tasks = Task.filter_by_pet(my_tasks, "Mochi")
		"""
		return [task for task in tasks if task.pet_name == pet_name]

	@staticmethod
	def filter_tasks(tasks: List['Task'], pet_name: Optional[str] = None, completed: Optional[bool] = None) -> List['Task']:
		"""Filter tasks by pet name and/or completion status.

		Args:
			tasks: List of Task objects to filter
			pet_name: Optional pet name to filter by
			completed: Optional completion status to filter by (True/False)

		Returns:
			New list of tasks matching the filter criteria

		Example:
			# Get incomplete tasks for Mochi
			mochi_incomplete = Task.filter_tasks(my_tasks, pet_name="Mochi", completed=False)

			# Get all completed tasks
			completed_tasks = Task.filter_tasks(my_tasks, completed=True)

			# Get all tasks for a specific pet
			buddy_tasks = Task.filter_tasks(my_tasks, pet_name="Buddy")
		"""
		filtered = tasks

		if pet_name is not None:
			filtered = [task for task in filtered if task.pet_name == pet_name]

		if completed is not None:
			filtered = [task for task in filtered if task.completed == completed]

		return filtered

	def clone_for_next_occurrence(self) -> Optional['Task']:
		"""Create a new task instance for the next occurrence of a recurring task.

		Returns None if this is not a recurring task.

		Example:
			daily_task = Task(title="Walk", duration=30, frequency=Frequency.DAILY, ...)
			tomorrow_task = daily_task.clone_for_next_occurrence()
		"""
		if not self.frequency:
			return None

		# Calculate next occurrence date
		next_date = self._calculate_next_date()
		if not next_date:
			return None

		# Create new task with same properties but new ID and date
		new_task = Task(
			title=self.title,
			duration=self.duration,
			priority=self.priority,
			pet_name=self.pet_name,
			is_recurring=self.is_recurring,
			preferred_time=self.preferred_time,
			time_constraint=self.time_constraint,
			schedule_constraint=ScheduleConstraint(
				earliest_start=self.schedule_constraint.earliest_start,
				latest_end=self.schedule_constraint.latest_end,
				hard_constraint=self.schedule_constraint.hard_constraint,
				source=self.schedule_constraint.source,
			),
			completed=False,  # New task starts incomplete
			frequency=self.frequency,
			scheduled_date=next_date,
			parent_task_id=self.parent_task_id or self.id,  # Link to original
			retrieval_sources=list(self.retrieval_sources),
			task_source=self.task_source,
			skipped=self.skipped,
			locked_preferred_time=self.locked_preferred_time,
		)

		return new_task

	def _calculate_next_date(self) -> Optional[date]:
		"""Calculate the next occurrence date based on frequency.

		Returns None if frequency is not set or scheduled_date is missing.
		"""
		if not self.frequency or not self.scheduled_date:
			return None

		current_date = self.scheduled_date

		if self.frequency == Frequency.DAILY:
			return current_date + timedelta(days=1)
		elif self.frequency == Frequency.WEEKLY:
			return current_date + timedelta(weeks=1)
		elif self.frequency == Frequency.BIWEEKLY:
			return current_date + timedelta(weeks=2)
		elif self.frequency == Frequency.MONTHLY:
			# Calculate next month properly (not just +30 days)
			# Handle month/year rollover
			if current_date.month == 12:
				next_year = current_date.year + 1
				next_month = 1
			else:
				next_year = current_date.year
				next_month = current_date.month + 1

			try:
				# Try to keep the same day of month
				return date(next_year, next_month, current_date.day)
			except ValueError:
				# Day doesn't exist in next month (e.g., Jan 31 -> Feb 31)
				# Use last day of the next month instead
				# Get first day of month after next, then subtract one day
				if next_month == 12:
					first_of_following_month = date(next_year + 1, 1, 1)
				else:
					first_of_following_month = date(next_year, next_month + 1, 1)
				return first_of_following_month - timedelta(days=1)

		return None

class Owner:
	def __init__(self, name: str):
		self.name = name
		self.pets: Dict[str, Pet] = {}  # Changed to dict for O(1) pet lookup
		self.task_index: Dict[str, Task] = {}  # Task ID -> Task for O(1) task lookup
		self.constraints: Dict[str, List[str]] = {}  # pet_name -> list of constraint descriptions
		self.timezone: str = "Local"
		self.availability_windows: List[tuple[time, time]] = []
		self.last_generation_summary: Dict[str, Any] = {}

	def set_timezone(self, timezone: str) -> bool:
		"""Set owner timezone string, returns True when accepted."""
		if not timezone or not timezone.strip():
			return False
		self.timezone = timezone.strip()
		return True

	def add_availability_window(self, start: time, end: time) -> tuple[bool, Optional[str]]:
		"""Add owner availability window used by scheduler."""
		if start >= end:
			return (False, "Availability start time must be earlier than end time.")
		self.availability_windows.append((start, end))
		self.availability_windows.sort(key=lambda window: window[0].strftime("%H:%M"))
		return (True, None)

	def clear_availability_windows(self) -> None:
		"""Clear all owner availability windows."""
		self.availability_windows = []

	def _build_constraint_from_window(self, start: Optional[time], end: Optional[time]) -> tuple[Optional[str], ScheduleConstraint]:
		"""Convert preferred window into scheduling constraint representation."""
		constraint = ScheduleConstraint(source="profile")
		constraint_text = None
		if start:
			constraint.earliest_start = start
		if end:
			constraint.latest_end = end
		if start and end:
			constraint_text = f"after {start.strftime('%H:%M')}"
		elif start:
			constraint_text = f"after {start.strftime('%H:%M')}"
		elif end:
			constraint_text = f"before {end.strftime('%H:%M')}"
		return constraint_text, constraint

	def _remove_generated_tasks_for_pet(self, pet_name: str) -> List[str]:
		"""Remove previously generated profile tasks for a pet before regeneration."""
		pet = self.get_pet(pet_name)
		if not pet:
			return []
		removed_titles: List[str] = []
		remaining_tasks = []
		for task in pet.tasks:
			if task.task_source == "profile_generated":
				removed_titles.append(task.title)
				self.task_index.pop(task.id, None)
			else:
				remaining_tasks.append(task)
		pet.tasks = remaining_tasks
		return removed_titles

	@staticmethod
	def _distribute_times(window_start: time, window_end: time, count: int) -> list[time]:
		"""Return `count` evenly-spaced times across [window_start, window_end].

		Divides the window into `count` equal slices and returns the midpoint
		of each slice, rounded to the nearest 5 minutes.
		"""
		if count <= 0:
			return []
		start_min = window_start.hour * 60 + window_start.minute
		end_min = window_end.hour * 60 + window_end.minute
		if end_min <= start_min:
			return []
		total = end_min - start_min
		slice_min = total / count
		result = []
		for i in range(count):
			mid = start_min + slice_min * (i + 0.5)
			rounded = round(mid / 5) * 5
			clamped = min(int(rounded), end_min)
			result.append(time(clamped // 60, clamped % 60))
		return result

	def generate_tasks_from_profile(self, pet_name: str, profile: RoutineProfile, replace_existing: bool = True) -> tuple[bool, int, Optional[str]]:
		"""Generate daily routine tasks from profile preferences.

		Returns (success, tasks_created, error).
		"""
		pet = self.get_pet(pet_name)
		if not pet:
			return (False, 0, f"Pet '{pet_name}' not found.")

		is_valid, error = profile.validate()
		if not is_valid:
			return (False, 0, error)

		if replace_existing:
			removed_titles = self._remove_generated_tasks_for_pet(pet_name)
		else:
			removed_titles = []

		created_count = 0
		created_titles: List[str] = []
		today = date.today()

		# Walk tasks
		walk_times = Owner._distribute_times(
			profile.walk_window_start, profile.walk_window_end, profile.walks_per_day,
		)
		for idx in range(profile.walks_per_day):
			title = "Exercise - Walk" if profile.walks_per_day == 1 else f"Exercise - Walk #{idx + 1}"
			time_constraint, schedule_constraint = self._build_constraint_from_window(
				profile.walk_window_start,
				profile.walk_window_end,
			)
			task = Task(
				title=title,
				duration=30,
				priority=Priority.HIGH,
				pet_name=pet_name,
				preferred_time=walk_times[idx] if walk_times else None,
				time_constraint=time_constraint,
				schedule_constraint=schedule_constraint,
				frequency=Frequency.DAILY,
				scheduled_date=today,
				task_source="profile_generated",
			)
			if self.add_task(pet_name, task):
				created_count += 1
				created_titles.append(task.title)

		# Meal tasks
		meal_times = Owner._distribute_times(
			profile.meal_window_start, profile.meal_window_end, profile.meals_per_day,
		)
		for idx in range(profile.meals_per_day):
			title = "Feeding - Meal" if profile.meals_per_day == 1 else f"Feeding - Meal #{idx + 1}"
			time_constraint, schedule_constraint = self._build_constraint_from_window(
				profile.meal_window_start,
				profile.meal_window_end,
			)
			task = Task(
				title=title,
				duration=15,
				priority=Priority.HIGH,
				pet_name=pet_name,
				preferred_time=meal_times[idx] if meal_times else None,
				time_constraint=time_constraint,
				schedule_constraint=schedule_constraint,
				frequency=Frequency.DAILY,
				scheduled_date=today,
				task_source="profile_generated",
			)
			if self.add_task(pet_name, task):
				created_count += 1
				created_titles.append(task.title)

		# Play/enrichment tasks
		play_times = Owner._distribute_times(
			profile.play_window_start, profile.play_window_end, profile.play_sessions_per_day,
		)
		for idx in range(profile.play_sessions_per_day):
			title = (
				"Enrichment - Play Session"
				if profile.play_sessions_per_day == 1
				else f"Enrichment - Play Session #{idx + 1}"
			)
			time_constraint, schedule_constraint = self._build_constraint_from_window(
				profile.play_window_start,
				profile.play_window_end,
			)
			task = Task(
				title=title,
				duration=20,
				priority=Priority.MEDIUM,
				pet_name=pet_name,
				preferred_time=play_times[idx] if play_times else None,
				time_constraint=time_constraint,
				schedule_constraint=schedule_constraint,
				frequency=Frequency.DAILY,
				scheduled_date=today,
				task_source="profile_generated",
			)
			if self.add_task(pet_name, task):
				created_count += 1
				created_titles.append(task.title)

		# Medication tasks
		for med_time in profile.medication_times:
			task = Task(
				title="Health - Medication",
				duration=10,
				priority=Priority.HIGH,
				pet_name=pet_name,
				preferred_time=med_time,
				frequency=Frequency.DAILY,
				scheduled_date=today,
				task_source="profile_generated",
			)
			if self.add_task(pet_name, task):
				created_count += 1
				created_titles.append(task.title)

		# Grooming tasks (weekly cadence)
		for idx in range(profile.grooming_sessions_per_week):
			title = "Care - Grooming" if profile.grooming_sessions_per_week == 1 else f"Care - Grooming #{idx + 1}"
			task = Task(
				title=title,
				duration=25,
				priority=Priority.LOW,
				pet_name=pet_name,
				frequency=Frequency.WEEKLY,
				scheduled_date=today,
				task_source="profile_generated",
			)
			if self.add_task(pet_name, task):
				created_count += 1
				created_titles.append(task.title)

		self.last_generation_summary = {
			'pet_name': pet_name,
			'created_count': created_count,
			'removed_count': len(removed_titles),
			'created_titles': created_titles,
			'removed_titles': removed_titles,
		}

		return (True, created_count, None)

	def add_pet(self, pet: Pet) -> None:
		"""Add a pet to the owner's pet list."""
		self.pets[pet.name] = pet
		# Index any existing tasks on the pet
		for task in pet.tasks:
			self.task_index[task.id] = task

	def get_pet(self, pet_name: str) -> Optional[Pet]:
		"""Retrieve a pet by name."""
		return self.pets.get(pet_name)

	def add_task(self, pet_name: str, task: Task) -> bool:
		"""Add a task to a specific pet's task list. Returns True if successful."""
		pet = self.get_pet(pet_name)
		if pet:
			is_valid, _ = task.validate_basic_fields()
			if not is_valid:
				return False
			is_valid, _ = task.validate_time_settings()
			if not is_valid:
				return False
			pet.add_task(task)
			self.task_index[task.id] = task  # Add to index for O(1) lookup
			return True
		return False

	def edit_task(self, task_id: str, **kwargs) -> bool:
		"""Edit a task's properties by task ID. Returns True if successful."""
		task = self.get_task_by_id(task_id)  # Use get_task_by_id which has fallback logic
		if task:
			for key, value in kwargs.items():
				if hasattr(task, key):
					setattr(task, key, value)
			return True
		return False

	def prune_old_completed_tasks(self) -> int:
		"""Remove completed tasks from a previous day. Returns count removed."""
		today = date.today()
		to_remove = [
			task.id
			for task in self.get_all_tasks()
			if task.completed and (task.scheduled_date is None or task.scheduled_date < today)
		]
		for task_id in to_remove:
			self.remove_task(task_id)
		return len(to_remove)

	def remove_task(self, task_id: str) -> bool:
		"""Remove a task by ID from its pet and the task index. Returns True if found."""
		task = self.get_task_by_id(task_id)
		if not task:
			return False
		pet = self.get_pet(task.pet_name)
		if pet:
			pet.tasks = [t for t in pet.tasks if t.id != task_id]
		self.task_index.pop(task_id, None)
		return True

	def remove_pet(self, pet_name: str) -> bool:
		"""Remove a pet and all its tasks. Returns True if found."""
		pet = self.pets.pop(pet_name, None)
		if pet is None:
			return False
		for task in pet.tasks:
			self.task_index.pop(task.id, None)
		self.constraints.pop(pet_name, None)
		return True

	def complete_task(self, task_id: str) -> tuple[bool, Optional[Task]]:
		"""Mark a task complete and generate next occurrence if recurring.

		Args:
			task_id: ID of the task to complete

		Returns:
			(success: bool, next_task: Optional[Task])
			- success: True if task was found and marked complete
			- next_task: The generated next occurrence task (if recurring), or None

		Example:
			success, next_task = owner.complete_task(task_id)
			if next_task:
				print(f"Next occurrence scheduled for {next_task.scheduled_date}")
		"""
		task = self.get_task_by_id(task_id)
		if not task:
			return (False, None)

		# Mark current task complete
		task.completed = True

		# If recurring, generate next occurrence
		next_task = None
		if task.frequency:
			next_task = task.clone_for_next_occurrence()

			if next_task:
				# Add next occurrence to the same pet
				pet = self.get_pet(task.pet_name)
				if pet:
					pet.add_task(next_task)
					self.task_index[next_task.id] = next_task

		return (True, next_task)

	def get_task_by_id(self, task_id: str) -> Optional[Task]:
		"""Retrieve a task by its ID across all pets."""
		# Try index first for O(1) lookup
		task = self.task_index.get(task_id)
		if task:
			return task
		# Fall back to searching if not in index (handles tasks added directly to pets)
		for pet in self.pets.values():
			task = pet.get_task_by_id(task_id)
			if task:
				# Add to index for future lookups
				self.task_index[task_id] = task
				return task
		return None

	def get_tasks_for_pet(self, pet_name: str) -> List[Task]:
		"""Get all tasks for a specific pet."""
		pet = self.get_pet(pet_name)
		return pet.tasks if pet else []

	def get_all_tasks(self) -> List[Task]:
		"""Get all tasks across all pets."""
		all_tasks = []
		for pet in self.pets.values():
			all_tasks.extend(pet.tasks)
		return all_tasks

	def add_constraint(self, pet_name: str, constraint: str) -> None:
		"""Add a scheduling constraint for a pet."""
		if pet_name not in self.constraints:
			self.constraints[pet_name] = []
		self.constraints[pet_name].append(constraint)

	def display_tasks(self) -> None:
		"""Display all tasks organized by pet."""
		if not self.pets:
			print("No pets registered.")
			return

		for pet in self.pets.values():
			print(f"\n{pet.name} ({pet.species}):")
			if not pet.tasks:
				print("  No tasks.")
			else:
				for task in pet.tasks:
					status = "✓" if task.completed else "○"
					print(f"  {status} [{task.priority.name}] {task.title} ({task.duration} min)")
					if task.preferred_time:
						print(f"      Preferred time: {task.preferred_time.strftime('%I:%M %p')}")
					if task.time_constraint:
						print(f"      Constraint: {task.time_constraint}")

class Scheduler:
	def __init__(self, owner: Owner):
		self.owner = owner  # Links scheduler to owner
		self.current_schedule: List[Dict] = []  # Stores generated schedule with explanations
		# Each dict includes decision metadata (rules, confidence, retrieval sources).
		self.schedule_confidence: float = 0.0
		self.guardrail_warnings: List[str] = []
		self.guidance_service = BreedGuidanceService()
		self.task_guidance: Dict[str, Dict[str, Any]] = {}
		self.rag_confidence_threshold: float = 0.5
		self.rag_enabled_current: bool = True

	def _parse_time_constraint(self, constraint: str) -> tuple[Optional[time], Optional[time]]:
		"""Parse time constraint string into time bounds.

		Examples: 'before 08:00' -> (None, 08:00), 'after 18:00' -> (18:00, None)
		Returns (earliest_time, latest_time)
		"""
		if not constraint:
			return (None, None)

		constraint = constraint.lower().strip()
		if "before" in constraint:
			time_str = constraint.split("before")[1].strip()
			hour, minute = map(int, time_str.split(":"))
			return (None, time(hour, minute))
		elif "after" in constraint:
			time_str = constraint.split("after")[1].strip()
			hour, minute = map(int, time_str.split(":"))
			return (time(hour, minute), None)
		return (None, None)

	def _time_to_minutes(self, t: time) -> int:
		"""Convert time to minutes since midnight for easier arithmetic."""
		return t.hour * 60 + t.minute

	def _minutes_to_time(self, minutes: int) -> time:
		"""Convert minutes since midnight back to time object."""
		hours = minutes // 60
		mins = minutes % 60
		return time(hours % 24, mins)

	_CATEGORY_SPREAD: dict[str, list[int]] = {
		"walk":      [9*60, 13*60, 17*60, 20*60],
		"meal":      [7*60, 12*60, 18*60],
		"medication": [8*60, 20*60],
		"play":      [10*60, 15*60, 19*60],
		"grooming":  [10*60, 14*60],
		"other":     [9*60, 13*60, 17*60, 20*60],
	}

	def _task_category(self, title: str) -> str:
		t = title.lower()
		if any(k in t for k in ("walk", "exercise", "run", "jog", "hike")):
			return "walk"
		if any(k in t for k in ("meal", "feed", "food", "breakfast", "dinner", "lunch", "treat")):
			return "meal"
		if any(k in t for k in ("medication", "medicine", "pill", "dose", "supplement")):
			return "medication"
		if any(k in t for k in ("play", "train", "training", "fetch", "toy", "sociali")):
			return "play"
		if any(k in t for k in ("groom", "brush", "bath", "bathe", "nail", "clean")):
			return "grooming"
		return "other"

	def _target_minute_for_task(self, task: Task, all_tasks: list) -> int:
		"""Return the ideal minute-of-day target for a task with no preferred time."""
		guidance = self.task_guidance.get(task.id, {})
		if guidance.get("rag_active"):
			earliest = guidance.get("earliest_start")
			latest = guidance.get("latest_end")
			if earliest and latest:
				return (self._time_to_minutes(earliest) + self._time_to_minutes(latest)) // 2
			if earliest:
				return self._time_to_minutes(earliest)
			if latest:
				return max(6 * 60, self._time_to_minutes(latest) - task.duration)

		category = self._task_category(task.title)
		spread = self._CATEGORY_SPREAD[category]
		same_cat_no_pref = [
			t for t in all_tasks
			if self._task_category(t.title) == category and not t.preferred_time
		]
		try:
			pos = same_cat_no_pref.index(task)
		except ValueError:
			pos = 0
		return spread[pos % len(spread)]

	def _resolve_task_time_bounds(self, task: Task) -> tuple[Optional[time], Optional[time]]:
		"""Resolve effective time bounds from structured constraint, then legacy string."""
		# Locked tasks: user's chosen time is absolute — no constraint check should block it
		if task.locked_preferred_time:
			return (None, None)

		if task.schedule_constraint.earliest_start or task.schedule_constraint.latest_end:
			return task.schedule_constraint.earliest_start, task.schedule_constraint.latest_end

		legacy_earliest, legacy_latest = self._parse_time_constraint(task.time_constraint)
		if legacy_earliest or legacy_latest:
			return legacy_earliest, legacy_latest

		guidance = self.task_guidance.get(task.id, {})
		if self.rag_enabled_current and guidance.get('rag_active'):
			return guidance.get('earliest_start'), guidance.get('latest_end')
		return (None, None)

	def _within_owner_availability(self, start_minutes: int, duration: int) -> bool:
		"""Check whether a task fits in at least one owner availability window."""
		windows = getattr(self.owner, 'availability_windows', [])
		if not windows:
			return True

		task_start = self._minutes_to_time(start_minutes)
		task_end = self._minutes_to_time(start_minutes + duration)
		for window_start, window_end in windows:
			if task_start >= window_start and task_end <= window_end:
				return True
		return False

	def _can_schedule_at(self, start_minutes: int, duration: int, task: Task) -> bool:
		"""Check if a task can be scheduled at a given time considering constraints."""
		earliest, latest = self._resolve_task_time_bounds(task)
		if not earliest and not latest:
			return True

		task_start = self._minutes_to_time(start_minutes)
		task_end = self._minutes_to_time(start_minutes + duration)

		if earliest and task_start < earliest:
			return False
		if latest and task_end > latest:
			return False
		return True

	def get_week_date_range(self, reference_date: Optional[date] = None) -> tuple[date, date]:
		"""Get Monday-Sunday range for week containing reference_date.

		Args:
			reference_date: Date to find week for (defaults to today)

		Returns:
			(monday_date, sunday_date)
		"""
		if reference_date is None:
			reference_date = date.today()

		# Get day of week (0=Monday, 6=Sunday)
		weekday = reference_date.weekday()

		# Calculate Monday and Sunday of current week
		monday = reference_date - timedelta(days=weekday)
		sunday = monday + timedelta(days=6)

		return (monday, sunday)

	def _resolve_schedule_conflicts(self, slot_duration: int = 15) -> None:
		"""Bump non-locked tasks that overlap with a higher-priority same-pet task."""
		# Build sorted list of scheduled items per pet
		from collections import defaultdict
		by_pet: dict[str, list] = defaultdict(list)
		for item in self.current_schedule:
			if item['time'] is not None:
				by_pet[item['pet_name']].append(item)

		for pet_items in by_pet.values():
			# Locked tasks sort before non-locked at the same minute so they're never bumped
			pet_items.sort(key=lambda x: (
				self._time_to_minutes(x['time']),
				0 if x['task'].locked_preferred_time else 1,
			))
			changed = True
			max_passes = 10
			passes = 0
			while changed and passes < max_passes:
				changed = False
				passes += 1
				for i in range(len(pet_items) - 1):
					a = pet_items[i]
					b = pet_items[i + 1]
					a_end = self._time_to_minutes(a['time']) + a['task'].duration + slot_duration
					b_start = self._time_to_minutes(b['time'])
					if b_start < a_end:
						# b overlaps a
						if b['task'].locked_preferred_time:
							# b is locked — try to bump a instead (a is guaranteed non-locked by sort)
							if not a['task'].locked_preferred_time:
								new_start = self._time_to_minutes(b['time']) + b['task'].duration + slot_duration
								if new_start + a['task'].duration <= 22 * 60:
									new_time = time(new_start // 60, new_start % 60)
									a['time'] = new_time
									a['reason'] = (
										a['reason'].rstrip('.') +
										f"; bumped to {new_time.strftime('%I:%M %p')} to resolve overlap with locked {b['task'].title}."
									)
									if 'conflict_resolved' not in a['applied_rules']:
										a['applied_rules'].append('conflict_resolved')
									pet_items.sort(key=lambda x: (
										self._time_to_minutes(x['time']),
										0 if x['task'].locked_preferred_time else 1,
									))
									changed = True
									break
							continue
						new_start = a_end
						if new_start + b['task'].duration <= 22 * 60:
							new_time = time(new_start // 60, new_start % 60)
							b['time'] = new_time
							b['reason'] = (
								b['reason'].rstrip('.') +
								f"; bumped to {new_time.strftime('%I:%M %p')} to resolve overlap with {a['task'].title}."
							)
							if 'conflict_resolved' not in b['applied_rules']:
								b['applied_rules'].append('conflict_resolved')
							pet_items.sort(key=lambda x: (
								self._time_to_minutes(x['time']),
								0 if x['task'].locked_preferred_time else 1,
							))
							changed = True
							break

	def generate_schedule(
		self,
		pet_name: Optional[str] = None,
		target_date: Optional[date] = None,
		enable_rag: bool = True,
	) -> List[Dict]:
		"""Generate a schedule for all tasks (or tasks for specific pet).

		Args:
			pet_name: Optional pet name to filter tasks
			target_date: Date to generate schedule for (defaults to today)

		Returns list of dicts with keys: task, time, pet_name, reason.
		Stores result in self.current_schedule for later explanation.
		"""
		self.current_schedule = []
		self.guardrail_warnings = []
		self.schedule_confidence = 0.0
		self.task_guidance = {}
		self.rag_enabled_current = enable_rag

		# Get tasks to schedule
		if pet_name:
			tasks = self.owner.get_tasks_for_pet(pet_name)
		else:
			tasks = self.owner.get_all_tasks()

		# Filter by scheduled date first: include target date + overdue + tasks without dates
		reference_date = target_date if target_date is not None else date.today()
		tasks = [
			t for t in tasks
			if t.scheduled_date is None or t.scheduled_date <= reference_date
		]

		# Filter out completed tasks UNLESS they're scheduled for today (target_date)
		# This allows today's completed tasks to show in the schedule with a completion indicator
		tasks = [
			t for t in tasks
			if not t.completed or (t.scheduled_date == reference_date)
		]

		# Skip tasks user excluded in generated-plan review.
		tasks = [t for t in tasks if not t.skipped]

		if not tasks:
			return self.current_schedule

		# Build RAG guidance context for each task.
		for task in tasks:
			if enable_rag:
				pet = self.owner.get_pet(task.pet_name)
				if pet:
					guidance = self.guidance_service.get_task_guidance(pet, task)
					rag_active = guidance.get('retrieval_confidence', 0.0) >= self.rag_confidence_threshold
					guidance['rag_active'] = rag_active
					if not rag_active:
						guidance['priority_boost'] = 0.0
						guidance['earliest_start'] = None
						guidance['latest_end'] = None
					self.task_guidance[task.id] = guidance
				else:
					self.task_guidance[task.id] = {
						'priority_boost': 0.0,
						'earliest_start': None,
						'latest_end': None,
						'sources': [],
						'reasons': [],
						'preferred_exercise_types': [],
						'energy_levels': [],
						'energy_level': None,
						'retrieval_confidence': 0.0,
						'rag_active': False,
						'has_guidance': False,
					}
			else:
				self.task_guidance[task.id] = {
					'priority_boost': 0.0,
					'earliest_start': None,
					'latest_end': None,
					'sources': [],
					'reasons': [],
					'preferred_exercise_types': [],
					'energy_levels': [],
					'energy_level': None,
					'retrieval_confidence': 0.0,
					'rag_active': False,
					'has_guidance': False,
				}

		# Sort tasks by priority (high to low), then by duration (longer first)
		sorted_tasks = sorted(
			tasks,
			key=lambda t: (t.priority.value + self.task_guidance.get(t.id, {}).get('priority_boost', 0.0), -t.duration),
			reverse=True
		)

		# Schedule tasks starting at 6 AM using time slot bitmap
		start_time = 6 * 60  # 6:00 AM in minutes
		max_time = 22 * 60  # 10 PM
		slot_duration = 15  # Each slot represents 15 minutes
		num_slots = (max_time - start_time) // slot_duration  # 64 slots (6 AM to 10 PM)

		# Initialize bitmap: False = available, True = occupied
		time_slots = [False] * num_slots

		# ── Phase 2.5: AI Day Planner ────────────────────────────────────────
		# Call Claude with the full task list for a globally-optimal plan.
		# Falls back to bitmap for any task Claude can't fit or if API unavailable.
		ai_assignments: dict = {}
		if enable_rag:
			try:
				from rag.ai_planner import plan_daily_schedule
				ai_result = plan_daily_schedule(
					tasks=tasks,
					task_guidance=self.task_guidance,
					owner=self.owner,
					target_date=reference_date,
				)
				if ai_result is not None:
					ai_assignments = ai_result
			except Exception:
				pass

		# Process AI-assigned tasks; collect tasks for bitmap fallback
		bitmap_tasks: list = []
		for task in sorted_tasks:
			ai_assignment = ai_assignments.get(task.id, {})
			assigned_time = ai_assignment.get("time") if isinstance(ai_assignment, dict) else ai_assignment
			ai_reason = ai_assignment.get("reason", "") if isinstance(ai_assignment, dict) else ""
			if assigned_time is None:
				bitmap_tasks.append(task)
				continue

			proposed_minutes = assigned_time.hour * 60 + assigned_time.minute
			slots_needed = (task.duration + slot_duration - 1) // slot_duration

			# Validate the AI assignment before trusting it
			if (self._can_schedule_at(proposed_minutes, task.duration, task)
					and self._within_owner_availability(proposed_minutes, task.duration)):

				slot = (proposed_minutes - start_time) // slot_duration
				if 0 <= slot <= num_slots - slots_needed:
					# Mark bitmap to prevent collision with fallback tasks
					for i in range(slot, slot + slots_needed):
						time_slots[i] = True

					# Build guidance profile
					guidance = self.task_guidance.get(task.id, {})
					retrieval_confidence = float(guidance.get('retrieval_confidence', 0.0))
					rag_is_active = bool(enable_rag and guidance.get('rag_active'))
					retrieval_sources = list(task.retrieval_sources)
					if rag_is_active:
						for source in guidance.get('sources', []):
							if source not in retrieval_sources:
								retrieval_sources.append(source)

					applied_rules = ['ai_planned']
					if rag_is_active:
						applied_rules.append('rag_guidance')
					if task.locked_preferred_time:
						applied_rules.append('locked_preferred_time')
					elif task.preferred_time:
						applied_rules.append('preferred_time')
					if getattr(self.owner, 'availability_windows', []):
						applied_rules.append('owner_availability')

					guidance_profile = {
						'energy_level': guidance.get('energy_level'),
						'preferred_exercise_types': list(guidance.get('preferred_exercise_types', [])),
						'retrieval_confidence': retrieval_confidence,
						'rag_active': rag_is_active,
						'guidance_source': 'ai_planned',
					}

					confidence_score = round(max(0.0, min(1.0, 0.95 - (0.05 if rag_is_active else 0.0))), 2)

					self.current_schedule.append({
						'task': task,
						'time': assigned_time,
						'pet_name': task.pet_name,
						'reason': ai_reason or f"AI-planned schedule: optimally placed considering all {len(tasks)} tasks for the day.",
						'applied_rules': applied_rules,
						'confidence_score': confidence_score,
						'retrieval_sources': retrieval_sources,
						'guidance_profile': guidance_profile,
					})
					continue

			# AI assignment failed validation — fall back to bitmap
			bitmap_tasks.append(task)

		# ── Bitmap loop (runs for all tasks when no API key, or as fallback) ──
		for task in bitmap_tasks:
			# Calculate how many 15-minute slots this task needs
			slots_needed = (task.duration + slot_duration - 1) // slot_duration  # Round up

			# Find a suitable time slot
			scheduled = False
			scheduled_time = None
			reason = ""

			# NEW: Try preferred time first
			applied_rules: List[str] = []
			confidence_score = 1.0
			guidance = self.task_guidance.get(task.id, {})
			retrieval_confidence = float(guidance.get('retrieval_confidence', 0.0))
			rag_is_active = bool(enable_rag and guidance.get('rag_active'))
			retrieval_sources = list(task.retrieval_sources)
			guidance_profile = {
				'energy_level': guidance.get('energy_level'),
				'preferred_exercise_types': list(guidance.get('preferred_exercise_types', [])),
				'retrieval_confidence': retrieval_confidence,
				'rag_active': rag_is_active,
				'guidance_source': guidance.get('guidance_source', 'retriever'),
			}
			if rag_is_active:
				for source in guidance.get('sources', []):
					if source not in retrieval_sources:
						retrieval_sources.append(source)

			if rag_is_active:
				applied_rules.append("rag_guidance")
				confidence_score -= 0.03
			elif enable_rag and guidance.get('has_guidance'):
				applied_rules.append("rag_fallback_low_confidence")
				self.guardrail_warnings.append(
					f"RAG fallback for task '{task.title}' (retrieval confidence {retrieval_confidence:.2f})"
				)

			if task.preferred_time:
				preferred_minutes = self._time_to_minutes(task.preferred_time)
				preferred_slot = (preferred_minutes - start_time) // slot_duration

				# Check if preferred slot is valid and available
				if 0 <= preferred_slot <= num_slots - slots_needed:
					if not any(time_slots[preferred_slot:preferred_slot + slots_needed]):
						# Check constraint compatibility (if constraint exists)
						if self._can_schedule_at(preferred_minutes, task.duration, task) and self._within_owner_availability(preferred_minutes, task.duration):
							# Schedule at preferred time
							for i in range(preferred_slot, preferred_slot + slots_needed):
								time_slots[i] = True

							# Smart break insertion
							if task.duration > 30 and preferred_slot + slots_needed < num_slots:
								time_slots[preferred_slot + slots_needed] = True

							scheduled = True
							scheduled_time = task.preferred_time
							reason = f"Scheduled at preferred time {task.preferred_time.strftime('%I:%M %p')}"
							applied_rules.append("preferred_time")

			# If task is locked to preferred time and could not be placed there, do not fallback.
			if task.locked_preferred_time and not scheduled:
				reason = "Could not schedule locked task at preferred time"
				self.guardrail_warnings.append(f"Locked task '{task.title}' could not be scheduled at preferred time")
				self.current_schedule.append({
					'task': task,
					'time': None,
					'pet_name': task.pet_name,
					'reason': reason,
					'applied_rules': ["locked_preferred_time", "unscheduled"],
					'confidence_score': 0.0,
					'retrieval_sources': retrieval_sources,
					'guidance_profile': guidance_profile,
				})
				continue

			# Fallback: search nearest to category/guidance target rather than greedy first-fit
			if not scheduled:
				if task.preferred_time:
					# Had a preferred time but it was unavailable — scan linearly as fallback
					search_order = range(num_slots - slots_needed + 1)
				else:
					# No preference: aim for a realistic spread across the day
					target_minute = self._target_minute_for_task(task, sorted_tasks)
					target_slot = max(0, min(
						(target_minute - start_time) // slot_duration,
						num_slots - slots_needed,
					))
					search_order = sorted(
						range(num_slots - slots_needed + 1),
						key=lambda s: abs(s - target_slot),
					)

				for slot_index in search_order:
					attempt_time = start_time + (slot_index * slot_duration)

					# Check if all required consecutive slots are free
					if not any(time_slots[slot_index:slot_index + slots_needed]):
						# Check if it meets time constraints
						if self._can_schedule_at(attempt_time, task.duration, task) and self._within_owner_availability(attempt_time, task.duration):
							# Mark slots as occupied
							for i in range(slot_index, slot_index + slots_needed):
								time_slots[i] = True

							# Smart break insertion: add 15-min break after tasks > 30 min
							if task.duration > 30 and slot_index + slots_needed < num_slots:
								time_slots[slot_index + slots_needed] = True

							scheduled = True
							scheduled_time = self._minutes_to_time(attempt_time)

							# Build reason
							if task.preferred_time:
								reason = f"Preferred time {task.preferred_time.strftime('%I:%M %p')} unavailable, scheduled based on {task.priority.name} priority"
								applied_rules.append("preferred_time_fallback")
								confidence_score -= 0.15
							else:
								reason = f"Scheduled based on {task.priority.name} priority"
								applied_rules.append("priority_sort")
							break  # Task scheduled, move to next task

			# Add common reason elements and schedule entry
			if scheduled:
				earliest, latest = self._resolve_task_time_bounds(task)
				if earliest or latest or task.time_constraint:
					constraint_text = task.time_constraint
					if not constraint_text:
						parts = []
						if earliest:
							parts.append(f"after {earliest.strftime('%H:%M')}")
						if latest:
							parts.append(f"before {latest.strftime('%H:%M')}")
						constraint_text = " and ".join(parts)
					reason += f" (constraint: {constraint_text})"
					applied_rules.append("time_constraint")
					confidence_score -= 0.05

				if rag_is_active and guidance.get('reasons'):
					reason += f". Guidance: {'; '.join(guidance['reasons'])}"
				if rag_is_active and guidance.get('energy_level'):
					reason += f" Energy profile: {guidance['energy_level']}."
				if rag_is_active and guidance.get('preferred_exercise_types'):
					reason += f" Suggested exercise types: {', '.join(guidance['preferred_exercise_types'])}."

				# Check for pet restrictions
				pet = self.owner.get_pet(task.pet_name)
				if pet and pet.restrictions:
					reason += f" considering pet restrictions: {', '.join(pet.restrictions)}"
					applied_rules.append("pet_restrictions")
					confidence_score -= 0.05

				if getattr(self.owner, 'availability_windows', []):
					applied_rules.append("owner_availability")
					confidence_score -= 0.05

				confidence_score = max(0.0, min(1.0, round(confidence_score, 2)))
				if confidence_score < 0.6:
					self.guardrail_warnings.append(
						f"Low confidence for task '{task.title}' ({confidence_score:.2f})"
					)

				self.current_schedule.append({
					'task': task,
					'time': scheduled_time,
					'pet_name': task.pet_name,
					'reason': reason,
					'applied_rules': applied_rules,
					'confidence_score': confidence_score,
					'retrieval_sources': retrieval_sources,
					'guidance_profile': guidance_profile,
				})

			if not scheduled:
				# Couldn't schedule this task
				reason = "Could not schedule due to time constraints, owner availability, or conflicts"
				if rag_is_active and guidance.get('reasons'):
					reason += f". Guidance considered: {'; '.join(guidance['reasons'])}"
				self.guardrail_warnings.append(f"Task '{task.title}' is unscheduled")
				self.current_schedule.append({
					'task': task,
					'time': None,
					'pet_name': task.pet_name,
					'reason': reason,
					'applied_rules': ["unscheduled"],
					'confidence_score': 0.0,
					'retrieval_sources': retrieval_sources,
					'guidance_profile': guidance_profile,
				})

		# ── Conflict resolution pass ─────────────────────────────────────────────
		# After AI planning + bitmap, bump same-pet overlaps for non-locked tasks.
		self._resolve_schedule_conflicts(slot_duration)

		# Sort schedule by time
		self.current_schedule.sort(key=lambda x: self._time_to_minutes(x['time']) if x['time'] else 9999)

		scheduled_items = [item for item in self.current_schedule if item['time'] is not None]
		if scheduled_items:
			self.schedule_confidence = round(
				sum(item.get('confidence_score', 0.0) for item in scheduled_items) / len(scheduled_items),
				2,
			)
		else:
			self.schedule_confidence = 0.0

		if self.schedule_confidence < 0.6 and self.current_schedule:
			self.guardrail_warnings.append(
				f"Overall schedule confidence is low ({self.schedule_confidence:.2f})"
			)

		return self.current_schedule

	def explain_schedule(self) -> str:
		"""Explain the reasoning behind the current schedule.

		Addresses bottleneck: now has access to self.current_schedule
		to explain the decisions made during generation.
		"""
		if not self.current_schedule:
			return "No schedule has been generated yet. Use generate_schedule() first."

		explanation = "=== Daily Care Schedule ===\n\n"

		for item in self.current_schedule:
			task = item['task']
			scheduled_time = item['time']
			pet_name = item['pet_name']
			reason = item['reason']
			confidence = item.get('confidence_score')
			applied_rules = item.get('applied_rules', [])
			retrieval_sources = item.get('retrieval_sources', [])
			guidance_profile = item.get('guidance_profile', {})

			# Show completion status
			status_indicator = "✅ COMPLETED - " if task.completed else ""

			if scheduled_time:
				explanation += f"⏰ {status_indicator}{scheduled_time.strftime('%I:%M %p')}\n"
			else:
				explanation += f"⏰ {status_indicator}NOT SCHEDULED\n"

			explanation += f"   Task: {task.title}\n"
			explanation += f"   Pet: {pet_name}\n"
			explanation += f"   Duration: {task.duration} minutes\n"
			explanation += f"   Priority: {task.priority.name}\n"
			explanation += f"   Why: {reason}\n\n"
			if confidence is not None:
				explanation += f"   Confidence: {confidence:.2f}\n"
			if applied_rules:
				explanation += f"   Rules: {', '.join(applied_rules)}\n"
			if retrieval_sources:
				explanation += f"   Sources: {', '.join(retrieval_sources)}\n"
			if guidance_profile.get('energy_level'):
				explanation += f"   Energy Level: {guidance_profile['energy_level']}\n"
			if guidance_profile.get('preferred_exercise_types'):
				explanation += (
					f"   Exercise Types: {', '.join(guidance_profile['preferred_exercise_types'])}\n"
				)
			explanation += "\n"

		# Add summary
		scheduled_count = sum(1 for item in self.current_schedule if item['time'] is not None)
		total_count = len(self.current_schedule)

		explanation += f"=== Summary ===\n"
		explanation += f"Scheduled: {scheduled_count}/{total_count} tasks\n"
		explanation += f"Schedule confidence: {self.schedule_confidence:.2f}\n"

		if scheduled_count < total_count:
			explanation += f"⚠️ {total_count - scheduled_count} task(s) could not be scheduled\n"
		if self.guardrail_warnings:
			explanation += "Guardrails:\n"
			for warning in self.guardrail_warnings:
				explanation += f"- {warning}\n"

		return explanation

	def get_reliability_report(self) -> Dict[str, Any]:
		"""Return reliability signals for UI and evaluation scripts."""
		low_confidence_tasks = [
			{
				'task': item['task'].title,
				'confidence_score': item.get('confidence_score', 0.0),
			}
			for item in self.current_schedule
			if item.get('confidence_score', 0.0) < 0.6
		]

		unscheduled = [item['task'].title for item in self.current_schedule if item['time'] is None]
		scheduled_count = len([item for item in self.current_schedule if item['time'] is not None])
		total_count = len(self.current_schedule)
		scheduled_ratio = (scheduled_count / total_count) if total_count > 0 else 0.0

		with_sources = sum(1 for item in self.current_schedule if len(item.get('retrieval_sources', [])) > 0)
		citation_coverage = (with_sources / total_count) if total_count > 0 else 0.0

		raw_constraint_violations = []
		if self.current_schedule:
			_, raw_constraint_violations = self.validate_schedule(self.current_schedule)
		constraint_violations = sum(1 for v in raw_constraint_violations if "violates constraint" in v)
		constraint_respect = 1.0
		if total_count > 0:
			constraint_respect = max(0.0, 1.0 - (constraint_violations / total_count))

		rag_active_tasks = sum(
			1
			for item in self.current_schedule
			if bool(item.get('guidance_profile', {}).get('rag_active'))
		)

		return {
			'total_tasks': total_count,
			'scheduled_tasks': scheduled_count,
			'unscheduled_tasks': unscheduled,
			'scheduled_ratio': round(scheduled_ratio, 2),
			'overall_confidence': self.schedule_confidence,
			'low_confidence_tasks': low_confidence_tasks,
			'citation_coverage': round(citation_coverage, 2),
			'constraint_respect': round(constraint_respect, 2),
			'rag_active_tasks': rag_active_tasks,
			'rag_fallback_count': len([w for w in self.guardrail_warnings if "RAG fallback" in w]),
			'guardrail_warnings': list(self.guardrail_warnings),
		}

	def validate_schedule(self, schedule: List[Dict]) -> tuple[bool, List[str]]:
		"""Validate a schedule against constraints.

		Returns (is_valid, list_of_violation_messages).
		"""
		violations = []

		# Check for overlapping tasks
		for i, item1 in enumerate(schedule):
			if item1['time'] is None:
				continue

			start1 = self._time_to_minutes(item1['time'])
			end1 = start1 + item1['task'].duration

			for item2 in schedule[i+1:]:
				if item2['time'] is None:
					continue

				start2 = self._time_to_minutes(item2['time'])
				end2 = start2 + item2['task'].duration

				# Check for overlap
				if not (end1 <= start2 or start1 >= end2):
					# Determine conflict type based on pet
					pet1 = item1['pet_name']
					pet2 = item2['pet_name']

					if pet1 == pet2:
						# Same pet conflict - more critical
						violations.append(
							f"⚠️ Same pet conflict: '{item1['task'].title}' and '{item2['task'].title}' "
							f"for {pet1} overlap at {item1['time'].strftime('%I:%M %p')} "
							f"({item1['task'].duration} min + {item2['task'].duration} min)"
						)
					else:
						# Different pets conflict - less critical but still a warning
						violations.append(
							f"ℹ️ Multi-pet conflict: '{item1['task'].title}' ({pet1}) and "
							f"'{item2['task'].title}' ({pet2}) overlap at {item1['time'].strftime('%I:%M %p')} "
							f"- you may need assistance with both pets"
						)

		# Check time constraints
		for item in schedule:
			if item['time'] is None:
				violations.append(f"Task '{item['task'].title}' is not scheduled")
				continue

			task = item['task']
			earliest, latest = self._resolve_task_time_bounds(task)
			if earliest or latest:
				task_time = item['time']
				task_end_minutes = self._time_to_minutes(task_time) + task.duration
				task_end_time = self._minutes_to_time(task_end_minutes)

				if earliest and task_time < earliest:
					violations.append(
						f"Task '{task.title}' scheduled at {task_time.strftime('%I:%M %p')} "
						f"violates constraint: {task.time_constraint}"
					)
				if latest and task_end_time > latest:
					violations.append(
						f"Task '{task.title}' ends at {task_end_time.strftime('%I:%M %p')} "
						f"violates constraint: {task.time_constraint}"
					)

			# Check owner availability windows
			if getattr(self.owner, 'availability_windows', []):
				task_time = item['time']
				task_end_minutes = self._time_to_minutes(task_time) + task.duration
				if not self._within_owner_availability(self._time_to_minutes(task_time), task.duration):
					violations.append(
						f"Task '{task.title}' scheduled at {task_time.strftime('%I:%M %p')} "
						f"falls outside owner availability windows"
					)

		return len(violations) == 0, violations

	def detect_preferred_time_conflicts(self) -> List[str]:
		"""Detect potential conflicts in preferred times before scheduling.

		Checks if tasks have overlapping preferred times, which may cause
		the scheduler to move one of them. This is a lightweight check that
		warns about potential scheduling issues.

		Returns list of warning messages.
		"""
		warnings = []
		all_tasks = self.owner.get_all_tasks()

		# Only check incomplete tasks with preferred times
		tasks_with_times = [
			t for t in all_tasks
			if not t.completed and t.preferred_time is not None
		]

		# Check all pairs for overlaps
		for i, task1 in enumerate(tasks_with_times):
			start1 = self._time_to_minutes(task1.preferred_time)
			end1 = start1 + task1.duration

			for task2 in tasks_with_times[i+1:]:
				start2 = self._time_to_minutes(task2.preferred_time)
				end2 = start2 + task2.duration

				# Check for overlap
				if not (end1 <= start2 or start1 >= end2):
					pet1 = task1.pet_name
					pet2 = task2.pet_name

					if pet1 == pet2:
						# Same pet - critical warning
						warnings.append(
							f"⚠️ Same pet conflict: '{task1.title}' and '{task2.title}' "
							f"for {pet1} both prefer {task1.preferred_time.strftime('%I:%M %p')} "
							f"(one will be rescheduled)"
						)
					else:
						# Different pets - informational warning
						warnings.append(
							f"ℹ️ Multi-pet conflict: '{task1.title}' ({pet1}) and '{task2.title}' ({pet2}) "
							f"both prefer {task1.preferred_time.strftime('%I:%M %p')} "
							f"- you may need help with both pets"
						)

		return warnings

	def detect_conflicts(self) -> List[str]:
		"""Identify any scheduling conflicts in current_schedule.

		Returns list of human-readable conflict warnings.
		Distinguishes between same-pet and multi-pet conflicts.
		"""
		_, violations = self.validate_schedule(self.current_schedule)
		return violations

	def get_conflict_summary(self) -> Dict[str, any]:
		"""Get detailed conflict analysis with categorization.

		Returns dictionary with:
		- total_conflicts: Total number of conflicts
		- same_pet_conflicts: Number of same-pet overlaps (critical)
		- multi_pet_conflicts: Number of different-pet overlaps (warning)
		- constraint_violations: Number of time constraint violations
		- unscheduled_tasks: Number of tasks that couldn't be scheduled
		- details: List of all violation messages
		"""
		violations = self.detect_conflicts()

		same_pet = sum(1 for v in violations if "Same pet conflict" in v)
		multi_pet = sum(1 for v in violations if "Multi-pet conflict" in v)
		constraint = sum(1 for v in violations if "violates constraint" in v)
		unscheduled = sum(1 for v in violations if "not scheduled" in v)

		return {
			'total_conflicts': len(violations),
			'same_pet_conflicts': same_pet,
			'multi_pet_conflicts': multi_pet,
			'constraint_violations': constraint,
			'unscheduled_tasks': unscheduled,
			'details': violations,
			'has_critical_issues': same_pet > 0 or unscheduled > 0
		}
