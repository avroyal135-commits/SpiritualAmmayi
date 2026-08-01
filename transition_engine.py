"""
transition_engine.py
=====================
Stitches a list of already-rendered, fixed-duration motion clips into a
single "top slideshow" video using FFmpeg's `xfade` filter, picking a
random (subtle, non-flashy) transition style between every pair of
clips.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import config
from utils import log, run_ffmpeg


@dataclass
class ClipSpec:
    path: Path
    duration: float


def pick_transitions(count: int, recent: Optional[List[str]] = None) -> List[str]:
    """Pick `count` transition names, softly avoiding recently used ones."""
    from utils import pick_avoiding_recent

    recent = recent or []
    chosen: List[str] = []
    for _ in range(count):
        t = pick_avoiding_recent(config.TRANSITION_TYPES, recent + chosen)
        chosen.append(t)
    return chosen


def build_slideshow(
    clips: List[ClipSpec],
    transitions: List[str],
    output_path: Path,
    width: int,
    height: int,
    fps: int = config.FPS,
    transition_duration: float = config.TRANSITION_DURATION,
) -> Path:
    """
    Chain `clips` (each already rendered at width x height / fps) with
    xfade transitions between consecutive pairs, writing the merged
    slideshow to `output_path`.
    """
    if not clips:
        raise ValueError("build_slideshow requires at least one clip")

    if len(clips) == 1:
        # Nothing to transition between -- just re-encode/copy through.
        run_ffmpeg(
            ["-i", str(clips[0].path), "-c", "copy", str(output_path)],
            description="Single clip short: copying through as slideshow",
        )
        return output_path

    if len(transitions) < len(clips) - 1:
        raise ValueError("Need at least len(clips)-1 transition names")

    inputs: List[str] = []
    for clip in clips:
        inputs += ["-i", str(clip.path)]

    filter_parts: List[str] = []
    running_duration = clips[0].duration
    last_label = "0"

    for i in range(1, len(clips)):
        transition_name = transitions[i - 1]
        offset = max(running_duration - transition_duration, 0.0)
        out_label = f"v{i}" if i < len(clips) - 1 else "vout"
        filter_parts.append(
            f"[{last_label}][{i}]xfade=transition={transition_name}:"
            f"duration={transition_duration:.3f}:offset={offset:.3f}[{out_label}]"
        )
        running_duration = running_duration + clips[i].duration - transition_duration
        last_label = out_label

    filter_complex = ";".join(filter_parts)

    run_ffmpeg(
        [
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{last_label}]",
            "-r", str(fps),
            "-an",
            "-c:v", config.VIDEO_CODEC,
            "-preset", config.VIDEO_PRESET,
            "-crf", str(config.VIDEO_CRF),
            str(output_path),
        ],
        description=f"Building slideshow from {len(clips)} clips with xfade transitions",
    )
    log.info("Slideshow written -> %s (approx %.2fs)", output_path.name, running_duration)
    return output_path
