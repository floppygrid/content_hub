"""
upload_daisy_and_the_dance_team.py — Launcher for Daisy and the dance team.
Handles both videos (YouTube + Facebook + Instagram + TikTok)
and photos (Facebook + Instagram + TikTok) in one script.

── Video commands ────────────────────────────────────────────────────────────
  python3 upload_daisy_and_the_dance_team.py                      # upload all pending videos
  python3 upload_daisy_and_the_dance_team.py --dry-run
  python3 upload_daisy_and_the_dance_team.py --limit 3
  python3 upload_daisy_and_the_dance_team.py --youtube-only
  python3 upload_daisy_and_the_dance_team.py --facebook-only
  python3 upload_daisy_and_the_dance_team.py --instagram-only
  python3 upload_daisy_and_the_dance_team.py --tiktok-only

── Photo commands ────────────────────────────────────────────────────────────
  python3 upload_daisy_and_the_dance_team.py --photos             # upload all pending photos
  python3 upload_daisy_and_the_dance_team.py --photos --dry-run
  python3 upload_daisy_and_the_dance_team.py --photos --limit 5
  python3 upload_daisy_and_the_dance_team.py --photos --facebook-only
  python3 upload_daisy_and_the_dance_team.py --photos --instagram-only
  python3 upload_daisy_and_the_dance_team.py --photos --tiktok-only

── Setup commands ────────────────────────────────────────────────────────────
  python3 upload_daisy_and_the_dance_team.py --setup              # Facebook + Instagram
  python3 upload_daisy_and_the_dance_team.py --setup-facebook
  python3 upload_daisy_and_the_dance_team.py --setup-instagram
  python3 upload_daisy_and_the_dance_team.py --setup-tiktok
  (YouTube authenticates automatically on first run — opens a browser)
"""

import argparse
import sys

# ─── Channel config ───────────────────────────────────────────────────────────

PROFILE_NAME  = "daisy-and-the-dance-team"
CREDS_FILE    = "meta_app_credentials.json"
FB_TOKEN_FILE = f"token_fb_{PROFILE_NAME}.json"
IG_TOKEN_FILE = f"token_ig_{PROFILE_NAME}.json"
TT_TOKEN_FILE = f"token_tt_{PROFILE_NAME}.json"

# Video config
VIDEO_CSV         = "videos_daisy_and_the_dance_team.csv"
VIDEO_FOLDER      = "videos_daisy_and_the_dance_team"
VIDEO_RESULTS     = f"upload_results_social_{PROFILE_NAME}.csv"
VIDEO_TT_RESULTS  = f"upload_results_tiktok_{PROFILE_NAME}.csv"
VIDEO_YT_RESULTS  = f"upload_results_yt_{PROFILE_NAME}.csv"

# Photo config
PHOTO_CSV         = "photos_daisy_and_the_dance_team - videos_books_pages_and_rain.csv"
PHOTO_FOLDER      = "photos_daisy_and_the_dance_team"
PHOTO_RESULTS     = f"upload_results_social_photos_{PROFILE_NAME}.csv"
PHOTO_TT_RESULTS  = f"upload_results_tiktok_photos_{PROFILE_NAME}.csv"

# ─── Import engine ────────────────────────────────────────────────────────────

try:
    from social_uploader import (
        setup_facebook, setup_instagram, setup_tiktok, run_upload_batch
    )
except ImportError:
    print("❌  social_uploader.py not found in the same directory.")
    sys.exit(1)

# ─── Parse args ───────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(
    description="Upload videos or photos for Daisy and the dance team"
)
parser.add_argument("--photos",          action="store_true", help="Upload photos instead of videos")
parser.add_argument("--setup",           action="store_true", help="Set up Facebook + Instagram")
parser.add_argument("--setup-facebook",  action="store_true", help="Set up Facebook only")
parser.add_argument("--setup-instagram", action="store_true", help="Set up Instagram only")
parser.add_argument("--setup-tiktok",    action="store_true", help="Set up TikTok only")
parser.add_argument("--dry-run",         action="store_true", help="Validate without uploading")
parser.add_argument("--youtube-only",    action="store_true", help="Post to YouTube only (videos only)")
parser.add_argument("--facebook-only",   action="store_true", help="Post to Facebook only")
parser.add_argument("--instagram-only",  action="store_true", help="Post to Instagram only")
parser.add_argument("--tiktok-only",     action="store_true", help="Post to TikTok only")
parser.add_argument("--limit",           type=int, default=0, help="Upload only this many items")
args = parser.parse_args()

# ─── Setup ────────────────────────────────────────────────────────────────────

if args.setup or args.setup_facebook:
    setup_facebook(CREDS_FILE, FB_TOKEN_FILE)

if args.setup or args.setup_instagram:
    setup_instagram(CREDS_FILE, IG_TOKEN_FILE)

if args.setup_tiktok:
    setup_tiktok(CREDS_FILE, TT_TOKEN_FILE)

# ─── Run ──────────────────────────────────────────────────────────────────────

if not (args.setup or args.setup_facebook or args.setup_instagram or args.setup_tiktok):
    if args.photos:
        # ── Photo batch ──
        run_upload_batch(
            creds_file      = CREDS_FILE,
            fb_token_file   = FB_TOKEN_FILE,
            ig_token_file   = IG_TOKEN_FILE,
            tt_token_file   = TT_TOKEN_FILE,
            csv_file        = PHOTO_CSV,
            videos_folder   = PHOTO_FOLDER,
            results_file    = PHOTO_RESULTS,
            tt_results_file = PHOTO_TT_RESULTS,
            dry_run         = args.dry_run,
            facebook_only   = args.facebook_only,
            instagram_only  = args.instagram_only,
            youtube_only    = False,        # photos don't go to YouTube
            tiktok_only     = args.tiktok_only,
            yt_profile      = "",           # no YouTube auth needed for photos
            yt_results_file = "",
            limit           = args.limit,
        )
    else:
        # ── Video batch ──
        run_upload_batch(
            creds_file      = CREDS_FILE,
            fb_token_file   = FB_TOKEN_FILE,
            ig_token_file   = IG_TOKEN_FILE,
            tt_token_file   = TT_TOKEN_FILE,
            csv_file        = VIDEO_CSV,
            videos_folder   = VIDEO_FOLDER,
            results_file    = VIDEO_RESULTS,
            tt_results_file = VIDEO_TT_RESULTS,
            dry_run         = args.dry_run,
            facebook_only   = args.facebook_only,
            instagram_only  = args.instagram_only,
            youtube_only    = args.youtube_only,
            tiktok_only     = args.tiktok_only,
            yt_profile      = PROFILE_NAME,
            yt_results_file = VIDEO_YT_RESULTS,
            limit           = args.limit,
        )
