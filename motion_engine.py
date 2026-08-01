"""
motion_engine.py
=================
Turns a single still image (or short video clip) into a fixed-duration,
fixed-resolution MP4 clip with one of several randomized "Ken Burns"
style motion effects, built entirely out of native FFmpeg filters
(zoompan, crop, rotate, eq, unsharp). No AI, no GPU.

Each call to `render_motion_clip` produces one self-contained clip that
`transition_engine.py` later stitches together with xfade transitions.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import config
from utils import is_video, log, run_ffmpeg


@dataclass
class MotionPlan:
    motion: str
    speed: float  # multiplier, SPEED_MIN..SPEED_MAX
    seed: float   # extra random phase used by "float" motion


def get_random_motion(recent: Optional[List[str]] = None) -> MotionPlan:
    """Pick a random motion type, softly avoiding recently used ones."""
    from utils import pick_avoiding_recent

    recent = recent or []
    motion = pick_avoiding_recent(config.MOTION_TYPES, recent)
    speed = round(random.uniform(config.SPEED_MIN, config.SPEED_MAX), 3)
    seed = round(random.uniform(0, 6.28318), 3)
    return MotionPlan(motion=motion, speed=speed, seed=seed)


def _enhancement_filters() -> str:
    """Shared subtle color + sharpen enhancement (FFmpeg-only, no AI)."""
    return (
        f"eq=saturation={config.EQ_SATURATION}:"
        f"contrast={config.EQ_CONTRAST}:"
        f"brightness={config.EQ_BRIGHTNESS},"
        f"unsharp=luma_msize_x=5:luma_msize_y=5:luma_amount={config.UNSHARP_LUMA_AMOUNT}"
    )


def _zoompan_expr(motion: str, duration_frames: int, speed: float, seed: float) -> tuple[str, str, str]:
    """
    Build (z, x, y) expressions for the zoompan filter for a given motion
    type. All expressions operate in terms of `on` (current output frame,
    0-indexed) and the baked-in total frame count `d`.
    """
    d = max(duration_frames, 1)
    zmin = config.ZOOM_MIN_FACTOR
    zmax = config.ZOOM_MAX_FACTOR
    travel = config.PAN_TRAVEL_FRACTION

    # progress fraction, sped up/slowed down by `speed`, clamped to [0,1]
    prog = f"min(1,(on/{d})*{speed})"

    if motion == "zoom_in":
        z = f"min(zoom+{(zmax - 1.0) / d * speed:.6f},{zmax})"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    elif motion == "zoom_out":
        z = f"if(lte(on,0),{zmax},max(zoom-{(zmax - 1.0) / d * speed:.6f},{zmin}))"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    elif motion == "pan_left":
        z = f"{1 + travel:.4f}"
        x = f"(iw-iw/zoom)*(1-{prog})"
        y = "(ih-ih/zoom)/2"

    elif motion == "pan_right":
        z = f"{1 + travel:.4f}"
        x = f"(iw-iw/zoom)*({prog})"
        y = "(ih-ih/zoom)/2"

    elif motion == "pan_up":
        z = f"{1 + travel:.4f}"
        x = "(iw-iw/zoom)/2"
        y = f"(ih-ih/zoom)*(1-{prog})"

    elif motion == "pan_down":
        z = f"{1 + travel:.4f}"
        x = "(iw-iw/zoom)/2"
        y = f"(ih-ih/zoom)*({prog})"

    elif motion == "diagonal_pan":
        z = f"{1 + travel:.4f}"
        x = f"(iw-iw/zoom)*({prog})"
        y = f"(ih-ih/zoom)*({prog})"

    elif motion == "float":
        amp = travel / 2
        z = f"{1 + travel:.4f}"
        x = f"(iw-iw/zoom)/2 + (iw-iw/zoom)*{amp:.4f}*sin(2*3.14159*(on/{d})*2+{seed})"
        y = f"(ih-ih/zoom)/2 + (ih-ih/zoom)*{amp:.4f}*cos(2*3.14159*(on/{d})*2+{seed})"

    elif motion == "micro_rotate":
        # Handled mostly by a separate rotate stage; zoompan just gives a
        # very mild constant zoom so rotation never reveals empty corners.
        z = f"{1 + travel * 1.6:.4f}"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    else:
        # Fallback: gentle zoom in
        z = f"min(zoom+{(zmax - 1.0) / d * speed:.6f},{zmax})"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    return z, x, y


def render_motion_clip(
    source: Path,
    output_path: Path,
    plan: MotionPlan,
    duration: float,
    width: int,
    height: int,
    fps: int = config.FPS,
) -> Path:
    """
    Render a single motion clip (image or video source) to `output_path`
    at exactly `duration` seconds, `width`x`height`, `fps`.
    """
    duration_frames = max(int(round(duration * fps)), 1)

    if is_video(source):
        _render_video_clip(source, output_path, duration, width, height, fps, plan)
    else:
        _render_image_clip(source, output_path, plan, duration_frames, duration, width, height, fps)

    log.info("Rendered motion clip [%s | %s] -> %s", source.name, plan.motion, output_path.name)
    return output_path


def _render_image_clip(
    source: Path,
    output_path: Path,
    plan: MotionPlan,
    duration_frames: int,
    duration: float,
    width: int,
    height: int,
    fps: int,
) -> None:
    z, x, y = _zoompan_expr(plan.motion, duration_frames, plan.speed, plan.seed)

    # Oversample the source so zoompan/crop/rotate always have enough
    # real pixel data and never reveal empty edges.
    oversample_w, oversample_h = width * 4, height * 4

    # micro_rotate needs zoompan to output a canvas LARGER than the final
    # target so that, after rotating, we can crop back down to the exact
    # target size without ever revealing empty/transparent corners. The
    # rotate filter's ow/oh cannot vary per frame (rotw()/roth() only
    # accept a fixed angle at filter-config time), so instead we keep the
    # canvas size fixed and rely on this safety margin.
    if plan.motion == "micro_rotate":
        rot_margin = 1.12
        zoompan_w, zoompan_h = int(width * rot_margin), int(height * rot_margin)
    else:
        zoompan_w, zoompan_h = width, height

    zoompan = (
        f"zoompan=z='{z}':x='{x}':y='{y}':d={duration_frames}:"
        f"s={zoompan_w}x{zoompan_h}:fps={fps}"
    )

    filters = [
        f"scale={oversample_w}:{oversample_h}:force_original_aspect_ratio=increase",
        f"crop={oversample_w}:{oversample_h}",
        zoompan,
    ]

    if plan.motion == "micro_rotate":
        max_deg = config.MICRO_ROTATE_DEGREES
        angle_expr = f"({max_deg}*PI/180)*sin(2*PI*(n/{duration_frames})*{plan.speed}+{plan.seed})"
        # Canvas size stays fixed (ow=iw, oh=ih, the defaults) -- the
        # zoompan margin above guarantees real pixels fill the corners
        # even at the maximum rotation angle. Crop back to the exact
        # target size, centered.
        filters.append(f"rotate={angle_expr}:fillcolor=black@0")
        filters.append(f"crop={width}:{height}")

    filters.append(_enhancement_filters())
    filters.append("format=yuv420p")

    vf = ",".join(filters)

    run_ffmpeg(
        [
            "-loop", "1", "-i", str(source),
            "-t", f"{duration:.3f}",
            "-vf", vf,
            "-r", str(fps),
            "-an",
            "-c:v", config.VIDEO_CODEC,
            "-preset", config.VIDEO_PRESET,
            "-crf", str(config.VIDEO_CRF),
            str(output_path),
        ],
        description=f"Rendering image motion clip ({plan.motion}) from {source.name}",
    )


def _render_video_clip(
    source: Path,
    output_path: Path,
    duration: float,
    width: int,
    height: int,
    fps: int,
    plan: MotionPlan,
) -> None:
    """
    Video source: cover-fit crop to the target frame, loop if shorter
    than the requested duration, apply the same color enhancement. A
    very gentle constant zoom is layered on so native video clips still
    feel dynamic and visually distinct from clip to clip.
    """
    from utils import ffprobe_duration, FFmpegError

    try:
        src_duration = ffprobe_duration(source)
    except FFmpegError:
        src_duration = duration

    needs_loop = src_duration < duration
    zoom_amt = round(1.0 + config.PAN_TRAVEL_FRACTION * 0.5, 4)

    filters = [
        f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase",
        f"crop={width * 2}:{height * 2}",
        f"scale={int(width * 2 * zoom_amt)}:{int(height * 2 * zoom_amt)}",
        f"crop={width}:{height}",
        _enhancement_filters(),
        "format=yuv420p",
    ]
    vf = ",".join(filters)

    input_args = ["-stream_loop", "-1", "-i", str(source)] if needs_loop else ["-i", str(source)]

    run_ffmpeg(
        [
            *input_args,
            "-t", f"{duration:.3f}",
            "-vf", vf,
            "-r", str(fps),
            "-an",
            "-c:v", config.VIDEO_CODEC,
            "-preset", config.VIDEO_PRESET,
            "-crf", str(config.VIDEO_CRF),
            str(output_path),
        ],
        description=f"Rendering native video clip from {source.name}",
    )
