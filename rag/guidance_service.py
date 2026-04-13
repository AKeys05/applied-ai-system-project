from datetime import time
from typing import Dict, Any, Optional

from rag.retriever import BreedGuidanceRetriever


class BreedGuidanceService:
    """Builds task-level scheduling hints from retrieved guidance."""

    def __init__(self):
        self.retriever = BreedGuidanceRetriever()
        self.energy_rank = {
            "low": 1,
            "low_to_medium": 2,
            "medium": 3,
            "medium_to_high": 4,
            "high": 5,
            "very_high": 6,
        }

    def _merge_window(
        self,
        current_start: Optional[time],
        current_end: Optional[time],
        candidate_start: Optional[time],
        candidate_end: Optional[time],
    ) -> tuple[Optional[time], Optional[time]]:
        merged_start = current_start
        merged_end = current_end

        if candidate_start:
            if merged_start is None or candidate_start > merged_start:
                merged_start = candidate_start
        if candidate_end:
            if merged_end is None or candidate_end < merged_end:
                merged_end = candidate_end

        return merged_start, merged_end

    def get_task_guidance(self, pet, task) -> Dict[str, Any]:
        entries = self.retriever.retrieve(
            species=getattr(pet, "species", ""),
            breed=getattr(pet, "breed", ""),
            task_title=getattr(task, "title", ""),
        )

        priority_boost = 0.0
        earliest_start = None
        latest_end = None
        sources = []
        reasons = []
        exercise_types = []
        energy_levels = []

        for entry in entries:
            priority_boost += float(entry.get("priority_boost", 0.0))
            earliest_start, latest_end = self._merge_window(
                earliest_start,
                latest_end,
                entry.get("earliest_start"),
                entry.get("latest_end"),
            )
            source = entry.get("source_id")
            if source and source not in sources:
                sources.append(source)
            reason = entry.get("reason")
            if reason and reason not in reasons:
                reasons.append(reason)
            for exercise in entry.get("preferred_exercise_types", []):
                if exercise not in exercise_types:
                    exercise_types.append(exercise)
            energy = entry.get("energy_level")
            if energy and energy not in energy_levels:
                energy_levels.append(energy)

        primary_energy_level = None
        if energy_levels:
            primary_energy_level = max(
                energy_levels,
                key=lambda level: self.energy_rank.get(level, 0),
            )

        return {
            "priority_boost": round(priority_boost, 2),
            "earliest_start": earliest_start,
            "latest_end": latest_end,
            "sources": sources,
            "reasons": reasons,
            "preferred_exercise_types": exercise_types,
            "energy_levels": energy_levels,
            "energy_level": primary_energy_level,
            "has_guidance": len(entries) > 0,
        }
