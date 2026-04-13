import json
from datetime import time
from pathlib import Path
from typing import Dict, List, Any, Optional


def _parse_hhmm(value: str) -> time:
    hour, minute = map(int, value.split(":"))
    return time(hour, minute)


class BreedGuidanceRetriever:
    """Simple retrieval over local breed/species guidance corpus."""

    def __init__(self, data_path: Optional[str] = None):
        if data_path is None:
            root = Path(__file__).resolve().parent.parent
            data_path = str(root / "data" / "breed_guidelines.json")

        with open(data_path, "r", encoding="utf-8") as file:
            self.guidelines = json.load(file)

    def _matching_rules(self, rules: List[Dict[str, Any]], task_title: str) -> List[Dict[str, Any]]:
        title = task_title.lower()
        matches = []
        for rule in rules:
            keywords = rule.get("task_keywords", [])
            if any(keyword in title for keyword in keywords):
                matches.append(rule)
        return matches

    def retrieve(self, species: str, breed: str, task_title: str) -> List[Dict[str, Any]]:
        """Retrieve matching guidance entries with source metadata and parsed windows."""
        species_key = (species or "").strip().lower()
        breed_key = (breed or "").strip().lower()
        results: List[Dict[str, Any]] = []

        species_entry = self.guidelines.get("species", {}).get(species_key)
        if species_entry:
            for rule in self._matching_rules(species_entry.get("rules", []), task_title):
                result = {
                    "source_id": species_entry.get("source_id", f"species:{species_key}:general"),
                    "priority_boost": float(rule.get("priority_boost", 0.0)),
                    "reason": rule.get("reason", "Species guidance applied."),
                    "energy_level": species_entry.get("energy_level"),
                    "preferred_exercise_types": species_entry.get("preferred_exercise_types", []),
                }
                window = rule.get("preferred_window")
                if window and "start" in window and "end" in window:
                    result["earliest_start"] = _parse_hhmm(window["start"])
                    result["latest_end"] = _parse_hhmm(window["end"])
                results.append(result)

        breed_entry = self.guidelines.get("breeds", {}).get(breed_key)
        if breed_entry:
            for rule in self._matching_rules(breed_entry.get("rules", []), task_title):
                result = {
                    "source_id": breed_entry.get("source_id", f"breed:{breed_key}:general"),
                    "priority_boost": float(rule.get("priority_boost", 0.0)),
                    "reason": rule.get("reason", "Breed guidance applied."),
                    "energy_level": breed_entry.get("energy_level"),
                    "preferred_exercise_types": breed_entry.get("preferred_exercise_types", []),
                }
                window = rule.get("preferred_window")
                if window and "start" in window and "end" in window:
                    result["earliest_start"] = _parse_hhmm(window["start"])
                    result["latest_end"] = _parse_hhmm(window["end"])
                results.append(result)

        return results
