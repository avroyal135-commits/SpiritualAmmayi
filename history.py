"""
history.py
==========
Maintains history.json so that consecutive runs of the generator do not
repeat the same god, bottom image, quote, transition style, or motion
style too soon. Each tracked category keeps a bounded, most-recent-first
list; only the most recent N (per config) are considered "recent" when
picking new assets, but the file keeps a longer tail for auditing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import config
from utils import log


class HistoryManager:
    """Loads, mutates, and persists history.json."""

    KEYS = ("gods", "bottom_images", "quotes", "transitions", "motions")

    def __init__(self, path: Path = config.HISTORY_FILE) -> None:
        self.path = path
        self.data: Dict[str, List[str]] = {key: [] for key in self.KEYS}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                for key in self.KEYS:
                    self.data[key] = list(loaded.get(key, []))
                log.info("Loaded history.json (%d gods, %d quotes tracked)",
                          len(self.data["gods"]), len(self.data["quotes"]))
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Could not read history.json (%s); starting fresh.", exc)
        else:
            log.info("No history.json found; starting fresh.")

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            log.info("Saved history.json")
        except OSError as exc:
            log.error("Failed to save history.json: %s", exc)

    def recent(self, key: str) -> List[str]:
        """Return the recent-window slice for a given tracked key."""
        window = {
            "gods": config.HISTORY_RECENT_GODS,
            "bottom_images": config.HISTORY_RECENT_BOTTOM_IMAGES,
            "quotes": config.HISTORY_RECENT_QUOTES,
            "transitions": config.HISTORY_RECENT_TRANSITIONS,
            "motions": config.HISTORY_RECENT_MOTIONS,
        }[key]
        return self.data[key][-window:]

    def record(self, key: str, value: str) -> None:
        """Append a used value and trim the stored list to a max length."""
        self.data[key].append(value)
        self.data[key] = self.data[key][-config.HISTORY_MAX_ENTRIES_PER_KEY:]

    def record_many(self, key: str, values: List[str]) -> None:
        for v in values:
            self.record(key, v)
