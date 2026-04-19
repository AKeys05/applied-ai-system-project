from datetime import time
from typing import Any, Dict, Optional

from rag.claude_advisor import get_scheduling_advice
from rag.retriever import BreedGuidanceRetriever


class BreedGuidanceService:
    """
    Builds task-level scheduling hints.

    Primary path: Claude API (claude-haiku) receives the pet profile and retrieved
    breed/species rules, then returns structured advice via tool use.

    Fallback path: keyword aggregation over the retrieved JSON entries, used when
    the API key is absent, the network is unavailable, or any call fails.
    """

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

    @staticmethod
    def _parse_hhmm(s: Optional[str]) -> Optional[time]:
        if not s:
            return None
        try:
            h, m = map(int, s.split(":"))
            return time(h, m)
        except Exception:
            return None

    def get_task_guidance(self, pet, task) -> Dict[str, Any]:
        entries = self.retriever.retrieve(
            species=getattr(pet, "species", ""),
            breed=getattr(pet, "breed", ""),
            task_title=getattr(task, "title", ""),
        )

        # --- Primary path: AI advisor (skipped when AI planner key is present) ---
        # When GROQ_API_KEY is set the day planner handles scheduling in one call;
        # per-task advisor calls are redundant and waste quota.
        import os
        claude_advice = None
        if not os.getenv("GROQ_API_KEY"):
            claude_advice = get_scheduling_advice(
                species=getattr(pet, "species", ""),
                breed=getattr(pet, "breed", ""),
                age_years=getattr(pet, "age_years", None),
                activity_level=getattr(pet, "activity_level", "medium"),
                task_title=getattr(task, "title", ""),
                task_duration=getattr(task, "duration", 30),
                retrieved_context=entries,
            )

        if claude_advice:
            source_ids = [e.get("source_id") for e in entries if e.get("source_id")]
            return {
                "priority_boost": round(min(1.0, float(claude_advice.get("priority_boost", 0.0))), 2),
                "earliest_start": self._parse_hhmm(claude_advice.get("window_start")),
                "latest_end": self._parse_hhmm(claude_advice.get("window_end")),
                "sources": source_ids,
                "reasons": claude_advice.get("reasons", []),
                "preferred_exercise_types": claude_advice.get("exercise_types", []),
                "energy_levels": [claude_advice["energy_level"]] if claude_advice.get("energy_level") else [],
                "energy_level": claude_advice.get("energy_level"),
                "retrieval_confidence": round(min(1.0, float(claude_advice.get("confidence", 0.0))), 2),
                "has_guidance": True,
                "guidance_source": "claude",
            }

        # --- Fallback path: keyword aggregation ---
        priority_boost = 0.0
        earliest_start = None
        latest_end = None
        sources: list[str] = []
        reasons: list[str] = []
        exercise_types: list[str] = []
        energy_levels: list[str] = []
        retrieval_confidence = 0.0

        for entry in entries:
            priority_boost += float(entry.get("priority_boost", 0.0))
            earliest_start, latest_end = self._merge_window(
                earliest_start, latest_end,
                entry.get("earliest_start"), entry.get("latest_end"),
            )
            source = entry.get("source_id")
            if source and source not in sources:
                sources.append(source)
            reason = entry.get("reason")
            if reason and reason not in reasons:
                reasons.append(reason)
            for ex in entry.get("preferred_exercise_types", []):
                if ex not in exercise_types:
                    exercise_types.append(ex)
            energy = entry.get("energy_level")
            if energy and energy not in energy_levels:
                energy_levels.append(energy)
            source_type = entry.get("source_type")
            if source_type == "breed":
                retrieval_confidence += 0.7
            elif source_type == "species":
                retrieval_confidence += 0.35

        primary_energy = None
        if energy_levels:
            primary_energy = max(energy_levels, key=lambda lv: self.energy_rank.get(lv, 0))

        return {
            "priority_boost": round(priority_boost, 2),
            "earliest_start": earliest_start,
            "latest_end": latest_end,
            "sources": sources,
            "reasons": reasons,
            "preferred_exercise_types": exercise_types,
            "energy_levels": energy_levels,
            "energy_level": primary_energy,
            "retrieval_confidence": min(1.0, round(retrieval_confidence, 2)),
            "has_guidance": len(entries) > 0,
            "guidance_source": "retriever",
        }
