"""
upload_photos_daisy_and_the_dance_team.py — Photo launcher for Daisy and the dance team.
Uploads images to Facebook, Instagram, and TikTok in a single run.
(YouTube is skipped — it does not support photo posts.)

CSV format: photos_daisy_and_the_dance_team - videos_books_pages_and_rain.csv
  Columns: file, social_media_description, tags, privacy, schedule_time,
           instagram, facebook, tiktok
  - 'file' column: filename WITHOUT extension (e.g. cute_cat_meme1)
    The .jpeg extension is added automatically when looking up the file.
  - After each successful upload the matching column gets a ✅ tick in the CSV.
  - Already-ticked rows are skipped on re-run.

Commands:
  python3 upload_photos_daisy_and_the_dance_team.py             # upload all pending photos
  python3 upload_photos_daisy_and_the_dance_team.py --dry-run   # validate without uploading
  python3 upload_photos_daisy_and_the_dance_team.py --limit 5   # upload only 5 photos
  python3 upload_photos_daisy_and_the_dance_team.py --facebook-only
  python3 upload_photos_daisy_and_the_dance_team.py --instagram-only
  python3 upload_photos_daisy_and_the_dance_team.py --tiktok-only

Note on Instagram:
  Instagram requires a publicly accessible image URL. This launcher handles it
  automatically by uploading to Facebook first and using Facebook's CDN URL for
  Instagram. For Instagram to work, Facebook must also be configured (or you can
  add an 'image_url' column to your CSV with a pre-hosted URL).
"""

import argparse
import sys
from pathlib import Path

# ─── Channel config ───────────────────────────────────────────────────────────

PROFILE_NAME    = "daisy-and-the-dance-team"
CSV_FILE        = "photos_daisy_and_the_dance_team - videos_books_pages_and_rain.csv"
PHOTOS_FOLDER   = "photos_daisy_and_the_dance_team"
CREDS_FILE      = "meta_app_credentials.json"
FB_TOKEN_FILE   = f"token_fb_{PROFILE_NAME}.json"
IG_TOKEN_FILE   = f"token_ig_{PROFILE_NAME}.json"
TT_TOKEN_FILE   = f"token_tt_{PROFILE_NAME}.json"
RESULTS_FILE    = f"upload_results_social_photos_{PROFILE_NAME}.csv"
TT_RESULTS_FILE = f"upload_results_tiktok_photos_{PROFILE_NAME}.csv"

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
    description="Upload photos to Facebook, Instagram & TikTok for Daisy and the dance team"
)
parser.add_argument("--setup",           action="store_true", help="Set up Facebook + Instagram")
parser.add_argument("--setup-facebook",  action="store_true", help="Set up Facebook only")
parser.add_argument("--setup-instagram", action="store_true", help="Set up Instagram only")
parser.add_argument("--setup-tiktok",    action="store_true", help="Set up TikTok only")
parser.add_argument("--dry-run",         action="store_true", help="Validate without uploading")
parser.add_argument("--facebook-only",   action="store_true", help="Post to Facebook only")
parser.add_argument("--instagram-only",  action="store_true", help="Post to Instagram only")
parser.add_argument("--tiktok-only",     action="store_true", help="Post to TikTok only")
parser.add_argument("--limit",           type=int, default=0, help="Upload only this many photos")
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
        videos_folder   = PHOTOS_FOLDER,      # photos folder
        results_file    = RESULTS_FILE,
        tt_results_file = TT_RESULTS_FILE,
        dry_run         = args.dry_run,
        facebook_only   = args.facebook_only,
        instagram_only  = args.instagram_only,
        youtube_only    = False,               # no YouTube for photos
        tiktok_only     = args.tiktok_only,
        yt_profile      = "",                  # no YouTube auth needed
        yt_results_file = "",
        limit           = args.limit,
    )
