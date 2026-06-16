"""
upload_daisy_and_the_dance_team.py — Launcher for Daisy and the dance team:
  YouTube + Facebook + Instagram + TikTok

Commands:
  python3 upload_daisy_and_the_dance_team.py                      # upload to all platforms
  python3 upload_daisy_and_the_dance_team.py --dry-run            # validate without uploading
  python3 upload_daisy_and_the_dance_team.py --limit 3            # upload only 3 videos
  python3 upload_daisy_and_the_dance_team.py --youtube-only       # YouTube only
  python3 upload_daisy_and_the_dance_team.py --facebook-only      # Facebook only
  python3 upload_daisy_and_the_dance_team.py --instagram-only     # Instagram only
  python3 upload_daisy_and_the_dance_team.py --tiktok-only        # TikTok only
  python3 upload_daisy_and_the_dance_team.py --setup              # set up Facebook + Instagram
  python3 upload_daisy_and_the_dance_team.py --setup-facebook     # set up Facebook only
  python3 upload_daisy_and_the_dance_team.py --setup-instagram    # set up Instagram only
  python3 upload_daisy_and_the_dance_team.py --setup-tiktok       # set up TikTok only
  (YouTube authenticates automatically on first run — opens a browser)
"""

import argparse
import sys
from pathlib import Path

# ─── Channel config ───────────────────────────────────────────────────────────

PROFILE_NAME     = "daisy-and-the-dance-team"
CSV_FILE         = "videos_daisy_and_the_dance_team.csv"
VIDEOS_FOLDER    = "videos_daisy_and_the_dance_team"
CREDS_FILE       = "meta_app_credentials.json"       # stores Meta + TikTok creds
FB_TOKEN_FILE    = f"token_fb_{PROFILE_NAME}.json"
IG_TOKEN_FILE    = f"token_ig_{PROFILE_NAME}.json"
TT_TOKEN_FILE    = f"token_tt_{PROFILE_NAME}.json"
RESULTS_FILE     = f"upload_results_social_{PROFILE_NAME}.csv"
TT_RESULTS_FILE  = f"upload_results_tiktok_{PROFILE_NAME}.csv"
YT_RESULTS_FILE  = f"upload_results_yt_{PROFILE_NAME}.csv"

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
    description="Upload videos to YouTube, Facebook, Instagram & TikTok for Daisy and the dance team"
)
parser.add_argument("--setup",            action="store_true", help="Set up Facebook + Instagram")
parser.add_argument("--setup-facebook",   action="store_true", help="Set up Facebook only")
parser.add_argument("--setup-instagram",  action="store_true", help="Set up Instagram only")
parser.add_argument("--setup-tiktok",     action="store_true", help="Set up TikTok only")
parser.add_argument("--dry-run",          action="store_true", help="Validate without uploading")
parser.add_argument("--youtube-only",     action="store_true", help="Post to YouTube only")
parser.add_argument("--facebook-only",    action="store_true", help="Post to Facebook only")
parser.add_argument("--instagram-only",   action="store_true", help="Post to Instagram only")
parser.add_argument("--tiktok-only",      action="store_true", help="Post to TikTok only")
parser.add_argument("--limit",            type=int, default=0, help="Upload only this many videos")
args = parser.parse_args()

# ─── Run ──────────────────────────────────────────────────────────────────────

if args.setup or args.setup_facebook:
    setup_facebook(CREDS_FILE, FB_TOKEN_FILE)

if args.setup or args.setup_instagram:
    setup_instagram(CREDS_FILE, IG_TOKEN_FILE)

if args.setup_tiktok:
    setup_tiktok(CREDS_FILE, TT_TOKEN_FILE)

if not (args.setup or args.setup_facebook or args.setup_instagram or args.setup_tiktok):
    run_upload_batch(
        creds_file      = CREDS_FILE,
        fb_token_file   = FB_TOKEN_FILE,
        ig_token_file   = IG_TOKEN_FILE,
        tt_token_file   = TT_TOKEN_FILE,
        csv_file        = CSV_FILE,
        videos_folder   = VIDEOS_FOLDER,
        results_file    = RESULTS_FILE,
        tt_results_file = TT_RESULTS_FILE,
        dry_run         = args.dry_run,
        facebook_only   = args.facebook_only,
        instagram_only  = args.instagram_only,
        youtube_only    = args.youtube_only,
        tiktok_only     = args.tiktok_only,
        yt_profile      = PROFILE_NAME,
        yt_results_file = YT_RESULTS_FILE,
        limit           = args.limit,
    )
