"""
utils.py
========
Shared utility functions: colorized logging, subprocess/FFmpeg wrappers,
media discovery helpers, and small generic helpers used across the
pipeline.
"""

from __future__ import annotations

import logging
import random
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, TypeVar

import config

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
class _ColorFormatter(logging.Formatter):
    """Minimal ANSI colorized formatter (no external dependency needed)."""

    COLORS = {
        logging.DEBUG: "\033[36m",     # cyan
        logging.INFO: "\033[32m",      # green
        logging.WARNING: "\033[33m",   # yellow
        logging.ERROR: "\033[31m",     # red
        logging.CRITICAL: "\033[41m",  # red background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        base = super().format(record)
        if sys.stdout.isatty() or True:
            # GitHub Actions log viewer renders ANSI colors fine.
            return f"{color}{base}{self.RESET}"
        return base


def setup_logging(name: str = "shorts_generator", level: int = logging.INFO) -> logging.Logger:
    """Configure and return a colorized logger. Safe to call multiple times."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    formatter = _ColorFormatter(
        fmt="[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


log = setup_logging()


# ---------------------------------------------------------------------------
# Subprocess / FFmpeg helpers
# ---------------------------------------------------------------------------
class FFmpegError(RuntimeError):
    """Raised when an FFmpeg (or FFprobe) invocation fails."""


def run_command(cmd: Sequence[str], description: str = "") -> str:
    """
    Run a subprocess command, raising FFmpegError with captured stderr on
    failure. Returns stdout on success.
    """
    if description:
        log.info(description)
    log.debug("Executing: %s", " ".join(str(c) for c in cmd))
    try:
        result = subprocess.run(
            list(map(str, cmd)),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as exc:
        log.error("Command failed (%s): %s", " ".join(map(str, cmd)), exc.stderr[-4000:])
        raise FFmpegError(exc.stderr) from exc
    except FileNotFoundError as exc:
        log.error("Binary not found while running: %s", " ".join(map(str, cmd)))
        raise FFmpegError(str(exc)) from exc


def run_ffmpeg(args: Sequence[str], description: str = "") -> None:
    """Run FFmpeg with standard overwrite + quiet-ish flags."""
    cmd = [config.FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "error", *args]
    run_command(cmd, description)


def ffprobe_duration(path: Path) -> float:
    """Return media duration in seconds using ffprobe."""
    cmd = [
        config.FFPROBE_BIN, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    out = run_command(cmd, description="")
    try:
        return float(out.strip())
    except ValueError:
        raise FFmpegError(f"Could not determine duration for {path}")


# ---------------------------------------------------------------------------
# Media discovery
# ---------------------------------------------------------------------------
def is_image(path: Path) -> bool:
    return path.suffix.lower() in config.IMAGE_EXTENSIONS


def is_video(path: Path) -> bool:
    return path.suffix.lower() in config.VIDEO_EXTENSIONS


def list_media_files(folder: Path) -> List[Path]:
    """Return all supported image/video files directly inside a folder."""
    if not folder.is_dir():
        return []
    valid_ext = set(config.IMAGE_EXTENSIONS) | set(config.VIDEO_EXTENSIONS)
    files = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in valid_ext
    )
    return files


def list_god_folders() -> List[Path]:
    """Return every god subfolder under assets/gods that contains media."""
    if not config.GODS_DIR.is_dir():
        return []
    folders = [
        p for p in sorted(config.GODS_DIR.iterdir())
        if p.is_dir() and list_media_files(p)
    ]
    return folders


def list_bottom_images() -> List[Path]:
    return list_media_files(config.BOTTOM_IMAGES_DIR)


def list_effect_files() -> List[Path]:
    if not config.EFFECTS_DIR.is_dir():
        return []
    return [p for p in sorted(config.EFFECTS_DIR.iterdir()) if is_video(p)]


def load_quotes(script_file: Path = config.SCRIPT_FILE) -> List[str]:
    """
    Parse assets/script.txt into a list of quotes. Quotes are separated
    by one or more blank lines and may themselves be multi-line.
    """
    if not script_file.exists():
        return []
    raw = script_file.read_text(encoding="utf-8")
    blocks = [b.strip("\n") for b in raw.replace("\r\n", "\n").split("\n\n")]
    quotes = [b.strip() for b in blocks if b.strip()]
    return quotes


# ---------------------------------------------------------------------------
# Random selection helpers (duplicate-avoidance aware)
# ---------------------------------------------------------------------------
def pick_avoiding_recent(items: Sequence[T], recent: Iterable[T]) -> T:
    """
    Pick a random item from `items`, preferring ones not present in
    `recent`. Falls back to the full pool if everything has been used
    recently (keeps the pipeline from ever stalling).
    """
    recent_set = set(recent)
    candidates = [i for i in items if i not in recent_set]
    pool = candidates if candidates else list(items)
    return random.choice(pool)


def pick_n_avoiding_recent(items: Sequence[T], recent: Iterable[T], n: int) -> List[T]:
    """Pick up to n unique items, preferring ones not in `recent`."""
    recent_set = set(recent)
    preferred = [i for i in items if i not in recent_set]
    random.shuffle(preferred)
    fallback = [i for i in items if i in recent_set]
    random.shuffle(fallback)
    ordered_pool = preferred + fallback
    n = min(n, len(items))
    return ordered_pool[:n]


from textwrap

import textwrap

def wrap_text(text: str, max_chars: int | None = None) -> str:
    """
    Automatically wrap Telugu/English text.

    Long quotes -> smaller line width.
    Short quotes -> larger line width.
    """

    text = text.strip()

    if max_chars is None:
        length = len(text)

        if length <= 35:
            max_chars = 18
        elif length <= 60:
            max_chars = 15
        elif length <= 90:
            max_chars = 12
        else:
            max_chars = 10

    wrapped = []

    for paragraph in text.split("\n"):
        wrapped.extend(
            textwrap.wrap(
                paragraph,
                width=max_chars,
                break_long_words=False,
                break_on_hyphens=False,
            )
        )

    return "\n".join(wrapped)
def get_quote_style(text: str):
    """
    Automatically choose font size, line spacing and wrap width
    based on quote length.
    """

    length = len(text)

    if length <= 35:
        return 54, 30, 18

    elif length <= 60:
        return 48, 28, 15

    elif length <= 90:
        return 42, 24, 12

    elif length <= 120:
        return 36, 20, 10

    else:
        return 32, 18, 9
