# Devotional Shorts Generator

Automatically generates devotional YouTube Shorts (720x1280, vertical)
entirely with **FFmpeg + lightweight Python** — no GPU, no CUDA, no
AI upscaling, no heavy ML models. Runs end-to-end on **GitHub-hosted
Ubuntu Actions runners**.

Each Short:

- Shows a randomized "Ken Burns" style slideshow/video of a chosen god
  in the **top 70%** of the frame (zoom, pan, float, micro-rotation,
  diagonal pan — FFmpeg `zoompan`/`crop`/`rotate` only)
- Stitches multiple clips together with a randomly chosen, subtle
  transition (fade, dissolve, wipe, circleopen, etc. via `xfade`)
- Shows a girl image + a Telugu devotional quote in the **bottom 30%**
  (text never covers the god)
- Optionally layers a particle/light/smoke/flowers overlay effect
  confined to the top region
- Optionally adds a low-opacity watermark bottom-right
- Ends with a 2-second "Subscribe" outro caption
- Generates a matching 1280x720 thumbnail with a golden border
- Generates title/description/hashtags/tags metadata as JSON
- Avoids repeating recently used gods, bottom images, quotes,
  transitions, and motion styles (`history.json`)
- Uploads the video, thumbnail, and metadata to Google Drive,
  organized as `Year / Month / Day / GodName`

You then manually download the video from Drive and upload it to
YouTube yourself (so you can add YouTube Music audio).

---

## 1. Folder structure

```
.
├── README.md
├── requirements.txt
├── config.py                  # all sizes/durations/paths/tunables
├── channel_config.json        # per-channel settings (no code changes needed)
├── prepare_assets.py          # validates assets/ before generating
├── motion_engine.py           # Ken Burns style FFmpeg motion filters
├── transition_engine.py       # xfade transition chaining
├── layout_engine.py           # top/bottom composite, overlays, watermark, outro
├── thumbnail.py                # 1280x720 golden-border thumbnail
├── metadata.py                 # title/description/hashtags/tags JSON
├── history.py                  # duplicate-avoidance (history.json)
├── drive_upload.py             # Google Drive service-account upload
├── utils.py                    # logging, ffmpeg wrapper, media discovery
├── generate_short.py           # main orchestrator (entry point)
├── assets/
│   ├── gods/
│   │   ├── shiva/              # jpg / jpeg / png / webp / mp4
│   │   ├── vishnu/
│   │   ├── krishna/
│   │   ├── hanuman/
│   │   ├── durga/
│   │   ├── ayyappa/
│   │   └── ganesh/
│   ├── bottom_images/          # girl1.jpg, girl2.png, ...
│   ├── script.txt              # Telugu quotes, blank-line separated
│   ├── fonts/
│   │   └── NotoSansTelugu-Bold.ttf
│   ├── effects/                # optional: particles.mp4, light.mp4, ...
│   └── logo/
│       └── logo.png            # optional watermark
├── output/                     # generated videos/thumbnails/metadata land here
├── history.json                # created/updated automatically
└── .github/workflows/generate.yml
```

## 2. Assets you must add before running

| Path | Required? | Notes |
|---|---|---|
| `assets/gods/<name>/*.jpg,.jpeg,.png,.webp,.mp4` | **Yes**, at least 1 folder with 1+ files | Image/video type auto-detected, no hardcoding |
| `assets/bottom_images/*.jpg,.png,.webp` | **Yes**, at least 1 | Girl images shown in the bottom 30% |
| `assets/script.txt` | **Yes**, at least 1 quote | Multi-line quotes separated by a blank line (already includes example Telugu quotes) |
| `assets/fonts/NotoSansTelugu-Bold.ttf` | **Yes** | Used for both the quote and the outro caption. Download it from [Google Fonts – Noto Sans Telugu](https://fonts.google.com/noto/specimen/Noto+Sans+Telugu) and place it at this exact path (or change the `font` field in `channel_config.json`) |
| `assets/effects/*.mp4` | Optional | particles.mp4, light.mp4, smoke.mp4, flowers.mp4 — skipped automatically if empty |
| `assets/logo/logo.png` | Optional | Watermark, skipped automatically if missing |

Run `python prepare_assets.py` any time to check what's missing — it
lists every problem clearly and exits non-zero if something required
is absent.

## 3. Local installation & run

```bash
# 1. System dependency
sudo apt-get update && sudo apt-get install -y ffmpeg   # Debian/Ubuntu
# macOS: brew install ffmpeg

# 2. Python dependencies (Python 3.11 recommended)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Add your assets (see table above)

# 4. Validate + generate
python prepare_assets.py
python generate_short.py
```

Generated files appear in `output/`:
`<god>_<run_id>.mp4`, `<god>_<run_id>_thumb.jpg`, `<god>_<run_id>_metadata.json`.

Without `GDRIVE_SERVICE_ACCOUNT_JSON` / `GDRIVE_ROOT_FOLDER_ID` set,
the Drive upload step is skipped automatically (useful for local
testing) — everything else still runs and writes to `output/`.

## 4. Google Drive setup (Service Account)

1. In [Google Cloud Console](https://console.cloud.google.com/), create
   (or reuse) a project and enable the **Google Drive API**.
2. Create a **Service Account**, then create a **JSON key** for it and
   download it.
3. In Google Drive, create a root folder (e.g. "God Shorts") and
   **share it** with the service account's email address
   (`...@...iam.gserviceaccount.com`) as an Editor.
4. Copy the folder ID from its URL:
   `https://drive.google.com/drive/folders/<THIS_IS_THE_ID>`

## 5. GitHub Secrets

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `GDRIVE_SERVICE_ACCOUNT_JSON` | Paste the **entire contents** of the service account JSON key file |
| `GDRIVE_ROOT_FOLDER_ID` | The Drive folder ID from step 4 above |

No other secrets are required.

## 6. GitHub Actions workflow

`.github/workflows/generate.yml`:

- Runs automatically every day (`cron: "0 3 * * *"` — edit to taste)
- Can also be triggered manually via **Actions → Generate Devotional
  Shorts → Run workflow**, optionally overriding `shorts_per_run` for
  that run only
- Installs FFmpeg + Python dependencies on the Ubuntu runner
- Validates assets (fails fast with a clear message if something is
  missing)
- Generates the configured number of Shorts
- Uploads video/thumbnail/metadata to Google Drive
- Also uploads everything as a downloadable **workflow artifact**
  (`output/**` + `history.json`) regardless of Drive upload success,
  so you always have a fallback copy
- Fails the job (red ❌, with logs) if generation fails for any short

To run it manually right now: go to the **Actions** tab → select
**Generate Devotional Shorts** → **Run workflow**.

## 7. Multi-channel reuse (`channel_config.json`)

To reuse this exact codebase for a different channel/language without
touching any Python code, just edit `channel_config.json`:

```json
{
  "channel_name": "Divine Blessings",
  "watermark": "@DivineBlessings",
  "outro_text": "🙏 Subscribe for Daily Blessings 🙏",
  "default_language": "te",
  "font": "NotoSansTelugu-Bold.ttf",
  "shorts_per_run": 2,
  "drive_folder": "God Shorts",
  "hashtags": ["#devotional", "#shorts", "#bhakti", "#god", "#temple", "#prayer"]
}
```

For a Tamil/Hindi/English channel: swap in the matching font under
`assets/fonts/`, update `font` and `default_language`, update
`assets/script.txt` with quotes in that language, and update
`outro_text` / `watermark` / `hashtags` as desired. Everything else
(motion engine, transitions, layout, thumbnail, Drive upload) works
unchanged.

## 8. How duplicate-avoidance works

`history.py` maintains `history.json` with the most recently used:
gods, bottom images, quotes, transitions, and motion styles. Each new
run prefers picking assets **not** in that recent window (sizes are
tunable in `config.py` via `HISTORY_RECENT_*`), falling back to the
full pool only if everything has been used recently — so the pipeline
never stalls, but back-to-back repeats are minimized.

## 9. Tuning

Everything tunable — video size, clip/transition durations, motion
speed range, zoom/pan amounts, enhancement strength, overlay/watermark
opacity, thumbnail styling, history window sizes — lives in
`config.py` with comments, so you never need to touch the pipeline
logic itself to adjust the look and feel.

## 10. Troubleshooting

- **"No god folders with media found"** — add at least one image or
  video under `assets/gods/<god-name>/`.
- **Font not found** — the Telugu `.ttf` must exist at exactly the
  path referenced by `channel_config.json`'s `font` field, under
  `assets/fonts/`.
- **Drive upload skipped** — check that both `GDRIVE_SERVICE_ACCOUNT_JSON`
  and `GDRIVE_ROOT_FOLDER_ID` are set as GitHub Secrets (or local env
  vars for a local run), and that the folder was shared with the
  service account's email.
- **Workflow fails on FFmpeg step** — GitHub's Ubuntu runners always
  have `apt` access; check the "Install FFmpeg" step logs for network
  issues on Anthropic-hosted mirrors (rare).
#   S p i r i t u a l A m m a y i  
 