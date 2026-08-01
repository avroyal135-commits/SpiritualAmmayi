"""
prepare_assets.py
==================
Run before `generate_short.py`. Validates that the assets/ folder is in
a usable state, creates any missing (but optional) directories, and
fails loudly with a clear message if something required is missing.

Usage:
    python prepare_assets.py
"""

from __future__ import annotations

import sys

import config
from utils import list_bottom_images, list_god_folders, load_quotes, log


class AssetValidationError(RuntimeError):
    pass


def validate() -> None:
    config.ensure_directories()

    problems: list[str] = []

    god_folders = list_god_folders()
    if not god_folders:
        problems.append(
            f"No god folders with media found under {config.GODS_DIR}. "
            "Add at least one subfolder (e.g. assets/gods/shiva/) containing "
            "jpg/jpeg/png/webp/mp4 files."
        )
    else:
        log.info("Found %d god folder(s): %s", len(god_folders), ", ".join(f.name for f in god_folders))

    bottom_images = list_bottom_images()
    if not bottom_images:
        problems.append(
            f"No bottom images found under {config.BOTTOM_IMAGES_DIR}. "
            "Add at least one girl image (jpg/jpeg/png/webp)."
        )
    else:
        log.info("Found %d bottom image(s).", len(bottom_images))

    quotes = load_quotes()
    if not quotes:
        problems.append(
            f"No quotes found in {config.SCRIPT_FILE}. Add at least one "
            "Telugu devotional quote (blank-line separated)."
        )
    else:
        log.info("Found %d quote(s) in script.txt.", len(quotes))

    channel_cfg = config.ChannelConfig.load()
    if not channel_cfg.font_path.exists():
        problems.append(
            f"Font file not found: {channel_cfg.font_path}. Add the Telugu "
            "font (e.g. NotoSansTelugu-Bold.ttf) under assets/fonts/."
        )
    else:
        log.info("Font found: %s", channel_cfg.font_path)

    # Optional dirs: effects/, logo/ -- fine if empty, just log status.
    from utils import list_effect_files
    effects = list_effect_files()
    log.info("Overlay effects available: %d (optional).", len(effects))
    log.info("Watermark logo present: %s (optional).", config.LOGO_FILE.exists())

    if problems:
        for p in problems:
            log.error("ASSET PROBLEM: %s", p)
        raise AssetValidationError(
            f"{len(problems)} asset problem(s) found. Fix the items above and re-run."
        )

    log.info("All required assets validated successfully. Ready to generate.")


if __name__ == "__main__":
    try:
        validate()
    except AssetValidationError as exc:
        log.error(str(exc))
        sys.exit(1)
