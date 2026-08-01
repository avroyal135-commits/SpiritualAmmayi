"""
thumbnail.py
============
Generates a 1280x720 YouTube-ready thumbnail for each Short:
  - a random frame grabbed from the final rendered video
  - a golden border
  - the god's name rendered in the devotional font

No AI upscaling — just FFmpeg (frame extraction) + Pillow (compositing).
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config
from utils import ffprobe_duration, log, run_ffmpeg


def _extract_random_frame(video_path: Path, output_path: Path) -> Path:
    duration = ffprobe_duration(video_path)
    # Avoid the very first/last few frames (often mid-transition/outro)
    lo = min(0.5, duration * 0.1)
    hi = max(lo, duration - 0.5)
    timestamp = random.uniform(lo, hi) if hi > lo else 0.0

    run_ffmpeg(
        [
            "-ss", f"{timestamp:.3f}",
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(output_path),
        ],
        description=f"Extracting thumbnail frame @ {timestamp:.2f}s",
    )
    return output_path


def _fit_font(draw: ImageDraw.ImageDraw, text: str, font_path: Path, max_width: int, start_size: int) -> ImageFont.FreeTypeFont:
    size = start_size
    while size > 20:
        font = ImageFont.truetype(str(font_path), size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 2
    return ImageFont.truetype(str(font_path), 20)


def generate_thumbnail(
    video_path: Path,
    god_name: str,
    font_path: Path,
    output_path: Path,
    temp_dir: Path,
) -> Path:
    """
    Extract a random frame from `video_path`, resize/crop to 1280x720,
    add a golden border and the god's name, and save to `output_path`.
    """
    temp_dir.mkdir(parents=True, exist_ok=True)
    raw_frame = temp_dir / "thumb_raw.jpg"
    _extract_random_frame(video_path, raw_frame)

    with Image.open(raw_frame) as im:
        im = im.convert("RGB")

        # Cover-fit crop to the thumbnail aspect ratio.
        target_ratio = config.THUMB_WIDTH / config.THUMB_HEIGHT
        src_ratio = im.width / im.height
        if src_ratio > target_ratio:
            new_width = int(im.height * target_ratio)
            offset = (im.width - new_width) // 2
            im = im.crop((offset, 0, offset + new_width, im.height))
        else:
            new_height = int(im.width / target_ratio)
            offset = (im.height - new_height) // 2
            im = im.crop((0, offset, im.width, offset + new_height))

        im = im.resize((config.THUMB_WIDTH, config.THUMB_HEIGHT), Image.LANCZOS)

        # Golden border
        bordered = Image.new(
            "RGB",
            (config.THUMB_WIDTH, config.THUMB_HEIGHT),
            config.THUMB_BORDER_COLOR,
        )
        inner_w = config.THUMB_WIDTH - 2 * config.THUMB_BORDER_WIDTH
        inner_h = config.THUMB_HEIGHT - 2 * config.THUMB_BORDER_WIDTH
        im_inner = im.resize((inner_w, inner_h), Image.LANCZOS)
        bordered.paste(im_inner, (config.THUMB_BORDER_WIDTH, config.THUMB_BORDER_WIDTH))

        # God-name caption with a translucent backing band for legibility
        draw = ImageDraw.Draw(bordered, "RGBA")
        label = god_name.strip().title()
        if font_path.exists():
            font = _fit_font(
                draw, label, font_path,
                max_width=config.THUMB_WIDTH - 2 * config.THUMB_TITLE_MARGIN,
                start_size=config.THUMB_TITLE_FONT_SIZE,
            )
        else:
            log.warning("Font %s not found; using default PIL font for thumbnail.", font_path)
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), label, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        band_h = text_h + 40
        draw.rectangle(
            [(0, config.THUMB_HEIGHT - band_h), (config.THUMB_WIDTH, config.THUMB_HEIGHT)],
            fill=(0, 0, 0, 140),
        )
        text_x = (config.THUMB_WIDTH - text_w) // 2
        text_y = config.THUMB_HEIGHT - band_h + 12
        draw.text(
            (text_x, text_y), label, font=font,
            fill=(255, 255, 255, 255),
            stroke_width=3, stroke_fill=(0, 0, 0, 255),
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        bordered.save(output_path, quality=92)

    log.info("Thumbnail generated -> %s", output_path.name)
    return output_path
