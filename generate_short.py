"""
generate_short.py
==================
Main entry point. Orchestrates the full pipeline for one or more
devotional Shorts (per channel_config.json's `shorts_per_run`):

  1. Pick a god (avoiding recently used ones)
  2. Pick a handful of that god's images/videos and render motion clips
  3. Stitch them into a slideshow with randomized transitions
  4. Build the bottom bar (girl image + Telugu quote)
  5. Composite the final 720x1280 vertical Short (+ optional overlay fx
     + optional watermark + outro caption)
  6. Generate a matching thumbnail
  7. Generate metadata (title/description/hashtags/tags)
  8. Update history.json to avoid near-term repeats
  9. Upload video + thumbnail + metadata to Google Drive

Usage:
    python generate_short.py
"""

from __future__ import annotations

import random
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

import config
import prepare_assets
from drive_upload import DriveUploader
from history import HistoryManager
from layout_engine import build_bottom_bar_image, compose_final_short
from metadata import build_metadata, save_metadata
from motion_engine import MotionPlan, get_random_motion, render_motion_clip
from thumbnail import generate_thumbnail
from transition_engine import ClipSpec, build_slideshow, pick_transitions
from utils import (
    list_bottom_images,
    list_effect_files,
    list_god_folders,
    list_media_files,
    load_quotes,
    log,
    pick_avoiding_recent,
)


def _select_clip_sources(god_folder: Path) -> List[Path]:
    files = list_media_files(god_folder)
    if not files:
        raise RuntimeError(f"God folder {god_folder} has no usable media files.")

    desired = random.randint(config.MIN_CLIPS_PER_SHORT, config.MAX_CLIPS_PER_SHORT)
    if len(files) >= desired:
        return random.sample(files, desired)
    # Not enough unique files: allow repeats so the slideshow still has
    # the desired number of clips/transitions.
    return [random.choice(files) for _ in range(desired)]


def _run_id() -> str:
    return f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def generate_one_short(
    channel_cfg: config.ChannelConfig,
    history: HistoryManager,
    drive: DriveUploader,
    run_id: str,
) -> None:
    temp_dir = config.TEMP_DIR / run_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # -- 1. Pick god -----------------------------------------------
        god_folders = list_god_folders()
        god_names = [f.name for f in god_folders]
        god_name = pick_avoiding_recent(god_names, history.recent("gods"))
        god_folder = next(f for f in god_folders if f.name == god_name)
        log.info("Selected god: %s", god_name)

        # -- 2. Render motion clips --------------------------------------
        sources = _select_clip_sources(god_folder)
        clips: List[ClipSpec] = []
        used_motions_this_run: List[str] = []

        for i, source in enumerate(sources):
            duration = round(random.uniform(config.MIN_CLIP_DURATION, config.MAX_CLIP_DURATION), 2)
            recent_motions = history.recent("motions") + used_motions_this_run
            plan: MotionPlan = get_random_motion(recent_motions)
            used_motions_this_run.append(plan.motion)

            clip_path = temp_dir / f"clip_{i:02d}.mp4"
            render_motion_clip(
                source=source,
                output_path=clip_path,
                plan=plan,
                duration=duration,
                width=config.VIDEO_WIDTH,
                height=config.TOP_HEIGHT,
            )
            clips.append(ClipSpec(path=clip_path, duration=duration))

        # -- 3. Transitions + slideshow ----------------------------------
        recent_transitions = history.recent("transitions")
        transitions = pick_transitions(len(clips) - 1, recent_transitions) if len(clips) > 1 else []
        slideshow_path = temp_dir / "slideshow.mp4"
        build_slideshow(
            clips=clips,
            transitions=transitions,
            output_path=slideshow_path,
            width=config.VIDEO_WIDTH,
            height=config.TOP_HEIGHT,
        )

        # -- 4. Bottom bar (girl + quote) --------------------------------
        bottom_images = [p.name for p in list_bottom_images()]
        if not bottom_images:
            raise RuntimeError("No bottom images available in assets/bottom_images/.")
        bottom_image_name = pick_avoiding_recent(bottom_images, history.recent("bottom_images"))
        bottom_image_path = config.BOTTOM_IMAGES_DIR / bottom_image_name

        quotes = load_quotes()
        if not quotes:
            raise RuntimeError("No quotes available in assets/script.txt.")
        quote = pick_avoiding_recent(quotes, history.recent("quotes"))

        bottom_bar_path = temp_dir / "bottom_bar.png"
        build_bottom_bar_image(
            girl_image=bottom_image_path,
            quote=quote,
            font_path=channel_cfg.font_path,
            width=config.VIDEO_WIDTH,
            height=config.BOTTOM_HEIGHT,
            output_path=bottom_bar_path,
            temp_dir=temp_dir,
        )

        # -- 5. Final composite -------------------------------------------
        overlay_files = list_effect_files()
        overlay_choice = random.choice(overlay_files) if overlay_files and random.random() < 0.6 else None
        watermark = config.LOGO_FILE if config.LOGO_FILE.exists() else None

        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        final_name = f"{god_name}_{run_id}"
        final_video_path = config.OUTPUT_DIR / f"{final_name}.mp4"

        compose_final_short(
            top_slideshow=slideshow_path,
            bottom_bar_image=bottom_bar_path,
            output_path=final_video_path,
            font_path=channel_cfg.font_path,
            outro_text=channel_cfg.outro_text,
            temp_dir=temp_dir,
            overlay_effect=overlay_choice,
            watermark_path=watermark,
        )

        # -- Sanity check: catch any filter-graph bug (e.g. an unlooped
        #    static-image input silently truncating the whole output) --
        from utils import ffprobe_duration
        actual_duration = ffprobe_duration(final_video_path)
        expected_min = sum(c.duration for c in clips) - (len(clips) - 1) * config.TRANSITION_DURATION
        if actual_duration < max(expected_min * 0.8, 1.0):
            raise RuntimeError(
                f"Final video duration sanity check failed: expected roughly "
                f"{expected_min:.2f}s, got {actual_duration:.2f}s. Aborting this short."
            )

        # -- 6. Thumbnail ---------------------------------------------------
        thumb_path = config.OUTPUT_DIR / f"{final_name}_thumb.jpg"
        generate_thumbnail(
            video_path=final_video_path,
            god_name=god_name,
            font_path=channel_cfg.font_path,
            output_path=thumb_path,
            temp_dir=temp_dir,
        )

        # -- 7. Metadata ------------------------------------------------
        metadata = build_metadata(god_name, channel_cfg)
        metadata_path = config.OUTPUT_DIR / f"{final_name}_metadata.json"
        save_metadata(metadata, metadata_path)

        # -- 8. History update --------------------------------------------
        history.record("gods", god_name)
        history.record("bottom_images", bottom_image_name)
        history.record("quotes", quote)
        history.record_many("transitions", transitions)
        history.record_many("motions", used_motions_this_run)

        # -- 9. Upload to Drive ---------------------------------------------
        drive.upload_short(god_name, final_video_path, thumb_path, metadata_path)

        log.info("Short complete: %s", final_video_path.name)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> None:
    config.ensure_directories()
    prepare_assets.validate()

    channel_cfg = config.ChannelConfig.load()
    log.info("Channel: %s | shorts_per_run=%d", channel_cfg.channel_name, channel_cfg.shorts_per_run)

    history = HistoryManager()
    drive = DriveUploader()

    failures = 0
    for n in range(channel_cfg.shorts_per_run):
        run_id = _run_id()
        log.info("=== Generating short %d/%d (run_id=%s) ===", n + 1, channel_cfg.shorts_per_run, run_id)
        try:
            generate_one_short(channel_cfg, history, drive, run_id)
        except Exception as exc:  # noqa: BLE001 - keep the run going for remaining shorts
            failures += 1
            log.error("Short %d/%d failed: %s", n + 1, channel_cfg.shorts_per_run, exc, exc_info=True)
        finally:
            history.save()

    if failures:
        log.error("%d of %d shorts failed this run.", failures, channel_cfg.shorts_per_run)
        sys.exit(1)

    log.info("All %d short(s) generated successfully.", channel_cfg.shorts_per_run)


if __name__ == "__main__":
    main()
