"""
config.py
=========
Central configuration for the Devotional Shorts Generator.

All paths, sizes, durations, and tunable parameters live here so that
no other module hardcodes a magic number. `channel_config.json` is
loaded on top of these defaults and can override channel-specific
values (watermark text, outro text, font, shorts-per-run, etc.)
without touching any Python code.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------
ROOT_DIR: Path = Path(__file__).resolve().parent

ASSETS_DIR: Path = ROOT_DIR / "assets"
GODS_DIR: Path = ASSETS_DIR / "gods"
BOTTOM_IMAGES_DIR: Path = ASSETS_DIR / "bottom_images"
SCRIPT_FILE: Path = ASSETS_DIR / "script.txt"
FONTS_DIR: Path = ASSETS_DIR / "fonts"
EFFECTS_DIR: Path = ASSETS_DIR / "effects"
LOGO_DIR: Path = ASSETS_DIR / "logo"
LOGO_FILE: Path = LOGO_DIR / "logo.png"

OUTPUT_DIR: Path = ROOT_DIR / "output"
TEMP_DIR: Path = ROOT_DIR / "temp"
HISTORY_FILE: Path = ROOT_DIR / "history.json"
CHANNEL_CONFIG_FILE: Path = ROOT_DIR / "channel_config.json"

# ---------------------------------------------------------------------------
# Supported file extensions
# ---------------------------------------------------------------------------
IMAGE_EXTENSIONS: List[str] = [".jpg", ".jpeg", ".png", ".webp"]
VIDEO_EXTENSIONS: List[str] = [".mp4", ".mov", ".m4v"]

# ---------------------------------------------------------------------------
# Video geometry
# ---------------------------------------------------------------------------
VIDEO_WIDTH: int = 720
VIDEO_HEIGHT: int = 1280

# 50% Top + 50% Bottom
# ---------------------------------------------------------------------------
# Video geometry
# ---------------------------------------------------------------------------

VIDEO_WIDTH: int = 720
VIDEO_HEIGHT: int = 1280

TOP_HEIGHT_RATIO: float = 0.50
BOTTOM_HEIGHT_RATIO: float = 0.50

TOP_HEIGHT: int = int(VIDEO_HEIGHT * TOP_HEIGHT_RATIO)   # 640
BOTTOM_HEIGHT: int = VIDEO_HEIGHT - TOP_HEIGHT           # 640

FPS: int = 30

# ---------------------------------------------------------------------------
# Durations (seconds)
# ---------------------------------------------------------------------------
# 8–9 clips

# ---------------------------------------------------------------------------
# Duration Settings
# ---------------------------------------------------------------------------

# More clips
MIN_CLIPS_PER_SHORT = 8
MAX_CLIPS_PER_SHORT = 10

# Every clip lasts longer
MIN_CLIP_DURATION = 5.0
MAX_CLIP_DURATION = 6.0

# Smooth transition
TRANSITION_DURATION = 0.8

# Longer outro
OUTRO_DURATION = 3.0
OUTRO_TEXT_DEFAULT = "🙏 Subscribe for Daily Blessings 🙏"
# Final target
TARGET_TOTAL_DURATION_MIN = 40.0
TARGET_TOTAL_DURATION_MAX = 45.0

# ---------------------------------------------------------------------------
# Motion engine
# ---------------------------------------------------------------------------
MOTION_TYPES: List[str] = [
    "zoom_in",
    "zoom_out",
    "pan_left",
    "pan_right",
    "pan_up",
    "pan_down",
    "float",
    "micro_rotate",
    "diagonal_pan",
]

# Zoom range applied over the lifetime of a clip
ZOOM_MIN_FACTOR: float = 1.05
ZOOM_MAX_FACTOR: float = 1.25

# Pan travel as a fraction of the oversized source that can be traversed
PAN_TRAVEL_FRACTION: float = 0.12

# Micro rotation bounds, degrees
MICRO_ROTATE_DEGREES: float = 1.6

# Random speed multiplier bounds applied to motion progress
SPEED_MIN: float = 0.35
SPEED_MAX: float = 0.60

# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------
TRANSITION_TYPES: List[str] = [
    "fade",
    "dissolve",
    "smoothleft",
    "smoothright",
    "circleopen",
    "fadeblack",
    "fadewhite",
    "wipeleft",
    "wiperight",
]

# ---------------------------------------------------------------------------
# Image / video enhancement (FFmpeg eq + unsharp only, no AI upscaling)
# ---------------------------------------------------------------------------
EQ_SATURATION: float = 1.12
EQ_CONTRAST: float = 1.06
EQ_BRIGHTNESS: float = 0.01
UNSHARP_LUMA_AMOUNT: float = 0.35

# ---------------------------------------------------------------------------
# Overlay effects
# ---------------------------------------------------------------------------
OVERLAY_OPACITY: float = 0.28

# ---------------------------------------------------------------------------
# Watermark
# ---------------------------------------------------------------------------
WATERMARK_OPACITY: float = 0.35
WATERMARK_MARGIN_PX: int = 24
WATERMARK_MAX_WIDTH_RATIO: float = 0.20  # fraction of video width

# ---------------------------------------------------------------------------
# Text (quote) styling
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Text (quote) styling
# ---------------------------------------------------------------------------
# Telugu quote
QUOTE_FONT_SIZE = 42
QUOTE_FONT_COLOR = "white"
QUOTE_BORDER_COLOR = "black"
QUOTE_BORDER_WIDTH = 6
OUTRO_FONT_SIZE = 56
OUTRO_FONT_COLOR = "yellow"
OUTRO_BORDER_COLOR = "black"
OUTRO_BORDER_WIDTH = 4

# More vertical spacing
QUOTE_LINE_SPACING = 38

# Wrap sooner
QUOTE_MAX_CHARS_PER_LINE = 12

# ---------------------------------------------------------------------------
# Thumbnail
# ---------------------------------------------------------------------------
THUMB_WIDTH: int = 1280
THUMB_HEIGHT: int = 720
THUMB_BORDER_COLOR: tuple = (212, 175, 55)  # golden
THUMB_BORDER_WIDTH: int = 18
THUMB_TITLE_FONT_SIZE: int = 64
THUMB_TITLE_MARGIN: int = 40

# ---------------------------------------------------------------------------
# Duplicate prevention (history)
# ---------------------------------------------------------------------------
HISTORY_RECENT_GODS: int = 3
HISTORY_RECENT_BOTTOM_IMAGES: int = 5
HISTORY_RECENT_QUOTES: int = 6
HISTORY_RECENT_TRANSITIONS: int = 4
HISTORY_RECENT_MOTIONS: int = 4
HISTORY_MAX_ENTRIES_PER_KEY: int = 50

# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------
GDRIVE_SERVICE_ACCOUNT_ENV: str = "GDRIVE_SERVICE_ACCOUNT_JSON"
GDRIVE_ROOT_FOLDER_ID_ENV: str = "GDRIVE_ROOT_FOLDER_ID"

# ---------------------------------------------------------------------------
# FFmpeg
# ---------------------------------------------------------------------------
FFMPEG_BIN: str = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN: str = os.environ.get("FFPROBE_BIN", "ffprobe")
VIDEO_CODEC: str = "libx264"
VIDEO_PRESET: str = "medium"
VIDEO_CRF: int = 20
PIXEL_FORMAT: str = "yuv420p"


@dataclass
class ChannelConfig:
    """Per-channel configuration loaded from channel_config.json."""

    channel_name: str = "Divine Blessings"
    watermark: str = "@DivineBlessings"
    outro_text: str = OUTRO_TEXT_DEFAULT
    default_language: str = "te"
    font: str = "NotoSansTelugu-Bold.ttf"
    shorts_per_run: int = 2
    drive_folder: str = "God Shorts"
    hashtags: List[str] = field(default_factory=lambda: [
        "#devotional", "#shorts", "#bhakti", "#god", "#temple", "#prayer",
    ])

    @property
    def font_path(self) -> Path:
        return FONTS_DIR / self.font

    @classmethod
    def load(cls, path: Path = CHANNEL_CONFIG_FILE) -> "ChannelConfig":
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        known_fields = {f for f in cls.__dataclass_fields__.keys()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


def ensure_directories() -> None:
    """Create all required directories if they do not already exist."""
    for path in (
        ASSETS_DIR, GODS_DIR, BOTTOM_IMAGES_DIR, FONTS_DIR,
        EFFECTS_DIR, LOGO_DIR, OUTPUT_DIR, TEMP_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
