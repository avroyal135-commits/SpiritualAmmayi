"""
metadata.py
===========
Builds the YouTube metadata JSON (title, description, hashtags, tags)
for a generated Short, ready to be pasted in manually or consumed by a
future auto-upload step.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from config import ChannelConfig

TITLE_TEMPLATES = [
    "\U0001F64F {god} Blessings | Daily Devotion Shorts",
    "{god} Darshan \u2764\ufe0f | Divine Blessings Shorts",
    "Feel the Grace of {god} \U0001F64F #Shorts",
    "{god} Devotional Short | Peace & Blessings",
    "Divine {god} Vibes \u2728 | Bhakti Shorts",
    "{god} Namah \U0001F64F | Daily Blessings",
]

DESCRIPTION_TEMPLATES = [
    (
        "\U0001F64F A short moment of devotion with {god}.\n"
        "May this bring peace, blessings, and positivity into your day.\n\n"
        "{channel_name} brings you daily devotional Shorts.\n"
        "Subscribe for daily blessings \U0001F64F\n"
    ),
    (
        "Experience the divine presence of {god} in this devotional Short.\n"
        "{channel_name} shares daily prayers and blessings to brighten your day.\n\n"
        "Subscribe & turn on notifications so you never miss a blessing \U0001F64F\n"
    ),
]

BASE_TAGS = [
    "devotional", "bhakti", "god", "temple", "prayer", "blessings",
    "spiritual", "hindu devotional", "daily devotion", "shorts",
]


def _god_tags(god_name: str) -> List[str]:
    g = god_name.lower()
    return [g, f"lord {g}", f"{g} bhakti", f"{g} devotional"]


def build_metadata(
    god_name: str,
    channel_config: ChannelConfig,
    extra_hashtags: List[str] | None = None,
) -> Dict:
    """Return a metadata dict (title, description, hashtags, tags, etc.)."""
    god_display = god_name.strip().title()

    title = random.choice(TITLE_TEMPLATES).format(god=god_display)
    description_body = random.choice(DESCRIPTION_TEMPLATES).format(
        god=god_display, channel_name=channel_config.channel_name
    )

    hashtags = list(dict.fromkeys(
        channel_config.hashtags
        + [f"#{god_name.lower()}"]
        + (extra_hashtags or [])
    ))
    hashtag_line = " ".join(hashtags)

    description = f"{description_body}\n{hashtag_line}"

    tags = list(dict.fromkeys(BASE_TAGS + _god_tags(god_name)))

    metadata = {
        "channel_name": channel_config.channel_name,
        "god": god_display,
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "tags": tags,
        "language": channel_config.default_language,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return metadata


def save_metadata(metadata: Dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, ensure_ascii=False, indent=2)
    return output_path
