"""
layout_engine.py
=================
Responsible for composing the final 720x1280 devotional Short.

Layout:
    • Top 50%  : God slideshow/video
    • Bottom 50% : Girl image + Telugu quote

    +-----------------------+
    |                       |
    |   God slideshow /     |   <- top 50%
    |   video (top 50%)     |
    |                       |
    +-----------------------+
    |  girl image + quote   |   <- bottom 50%
    +-----------------------+

Also layers in optional particle/light overlay effects (confined to the
top region only, so the devotional quote stays fully legible), an
optional low-opacity watermark, and a 2-second outro caption at the end.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import config
from utils import (
    log,
    run_ffmpeg,
    wrap_text,
    ffprobe_duration,
    get_quote_style,
)


def _escape_path_for_filter(path: Path) -> str:
    s = str(path)
    s = s.replace("\\", "\\\\")
    s = s.replace(":", "\\:")
    s = s.replace("'", "\\'")
    return s


def build_bottom_bar_image(
    girl_image: Path,
    quote: str,
    font_path: Path,
    width: int,
    height: int,
    output_path: Path,
    temp_dir: Path,
) -> Path:
    """
    Render the static bottom-bar PNG: the girl image cover-cropped to
    width x height, with the Telugu devotional quote drawn centered on
    top of it (bordered text for legibility against any background).
    """
    temp_dir.mkdir(parents=True, exist_ok=True)
    font_size, line_spacing, wrap_width = get_quote_style(quote)

    quote_wrapped = wrap_text(quote, wrap_width)
    quote_file = temp_dir / "quote.txt"
    quote_file.write_text(quote_wrapped, encoding="utf-8")

    fontfile = _escape_path_for_filter(font_path)
    textfile = _escape_path_for_filter(quote_file)

    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        # Subtle darken so white bordered text stays legible on any photo
        f"eq=brightness=-0.06,"
        f"drawtext=fontfile={fontfile}:textfile={textfile}:"
        f"fontcolor={config.QUOTE_FONT_COLOR}:"
        f"fontsize={font_size}:"
        f"bordercolor={config.QUOTE_BORDER_COLOR}:"
        f"borderw={config.QUOTE_BORDER_WIDTH}:"
        f"line_spacing={line_spacing}:"
        f"x=(w-text_w)/2:"
        f"y=(h-text_h)/2"
    )

    run_ffmpeg(
        [
            "-i", str(girl_image),
            "-vf", vf,
            "-frames:v", "1",
            str(output_path),
        ],
        description=f"Building bottom bar (girl image + quote) from {girl_image.name}",
    )
    return output_path


def compose_final_short(
    top_slideshow: Path,
    bottom_bar_image: Path,
    output_path: Path,
    font_path: Path,
    outro_text: str,
    temp_dir: Path,
    overlay_effect: Optional[Path] = None,
    watermark_path: Optional[Path] = None,
    width: int = config.VIDEO_WIDTH,
    top_height: int = config.TOP_HEIGHT,
    bottom_height: int = config.BOTTOM_HEIGHT,
    fps: int = config.FPS,
) -> Path:
    """
    Combine the top slideshow + bottom bar (+ optional overlay effect,
    watermark, outro text) into the final 720x1280 vertical Short.
    """
    total_duration = ffprobe_duration(top_slideshow)

    outro_wrapped = wrap_text(outro_text, config.QUOTE_MAX_CHARS_PER_LINE + 4)
    outro_file = temp_dir / "outro.txt"
    outro_file.write_text(outro_wrapped, encoding="utf-8")
    outro_fontfile = _escape_path_for_filter(font_path)
    outro_textfile = _escape_path_for_filter(outro_file)

    inputs = ["-i", str(top_slideshow), "-loop", "1", "-i", str(bottom_bar_image)]
    input_index = 2
    overlay_idx: Optional[int] = None
    watermark_idx: Optional[int] = None

    if overlay_effect is not None and overlay_effect.exists():
        inputs += ["-stream_loop", "-1", "-i", str(overlay_effect)]
        overlay_idx = input_index
        input_index += 1

    if watermark_path is not None and watermark_path.exists():
        # -loop 1: the watermark is a single static image; without looping
        # it, it supplies exactly one frame and (combined with overlay's
        # shortest behaviour) would truncate the whole output to 1 frame.
        inputs += ["-loop", "1", "-i", str(watermark_path)]
        watermark_idx = input_index
        input_index += 1

    filter_steps = []

    # 1) Bottom bar: static image -> fixed-duration video stream



    filter_steps.append(
        f"[1:v]"
        f"loop=-1:size=1:start=0,"
        f"fps={fps},"
        f"trim=duration={total_duration:.3f},"
        f"setpts=PTS-STARTPTS[bottombar]"
    )

    # 2) Stack top (god) + bottom (girl/quote) vertically
    filter_steps.append(f"[0:v][bottombar]vstack=inputs=2[stacked]")
    current = "stacked"

    # 3) Optional overlay effect, confined to the TOP region only so the
    #    quote text is never obscured.
    if overlay_idx is not None:
        filter_steps.append(
            f"[{overlay_idx}:v]trim=duration={total_duration:.3f},setpts=PTS-STARTPTS,"
            f"scale={width}:{top_height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{top_height},format=rgba,"
            f"colorchannelmixer=aa={config.OVERLAY_OPACITY}[fx]"
        )
        filter_steps.append(f"[{current}][fx]overlay=x=0:y=0[with_fx]")
        current = "with_fx"

    # 4) Outro caption, last OUTRO_DURATION seconds, near bottom of the
    #    top (god) region so it never collides with the quote below it.
    outro_y = top_height - 140
    outro_start = max(total_duration - config.OUTRO_DURATION, 0.0)
    filter_steps.append(
        f"[{current}]drawtext=fontfile={outro_fontfile}:textfile={outro_textfile}:"
        f"fontcolor={config.OUTRO_FONT_COLOR}:fontsize={config.OUTRO_FONT_SIZE}:"
        f"bordercolor={config.OUTRO_BORDER_COLOR}:borderw={config.OUTRO_BORDER_WIDTH}:"
        f"box=1:boxcolor=black@0.45:boxborderw=18:"
        f"x=(w-text_w)/2:y={outro_y}:"
        f"enable='between(t,{outro_start:.3f},{total_duration:.3f})'[with_outro]"
    )
    current = "with_outro"

    # 5) Optional low-opacity watermark, bottom-right corner, full frame.
    if watermark_idx is not None:
        max_w = int(width * config.WATERMARK_MAX_WIDTH_RATIO)
        filter_steps.append(
            f"[{watermark_idx}:v]scale={max_w}:-1,format=rgba,"
            f"colorchannelmixer=aa={config.WATERMARK_OPACITY}[wm]"
        )
        filter_steps.append(
            f"[{current}][wm]overlay=x=W-w-{config.WATERMARK_MARGIN_PX}:"
            f"y=H-h-{config.WATERMARK_MARGIN_PX}[final]"
        )
        current = "final"

    filter_complex = ";".join(filter_steps)

    run_ffmpeg(
        [
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{current}]",
            "-t", f"{total_duration:.3f}",
            "-r", str(fps),
            "-an",
            "-c:v", config.VIDEO_CODEC,
            "-preset", config.VIDEO_PRESET,
            "-crf", str(config.VIDEO_CRF),
            "-pix_fmt", config.PIXEL_FORMAT,
            str(output_path),
        ],
        description="Compositing final vertical Short",
    )
    log.info("Final short written -> %s (%.2fs)", output_path.name, total_duration)
    return output_path
