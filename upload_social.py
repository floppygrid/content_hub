"""
upload_social.py — Run all channels in one go:
  • Books Pages and Rain    (videos → YouTube + Facebook + Instagram + TikTok)
  • Daisy and the Dance Team (videos → YouTube + Facebook + Instagram + TikTok)
  • Daisy and the Dance Team (photos → Facebook + Instagram + TikTok)

Commands:
  python3 upload_social.py                      # upload everything pending across all channels
  python3 upload_social.py --dry-run            # validate without uploading
  python3 upload_social.py --limit 3            # upload only 3 items per channel
  python3 upload_social.py --youtube-only
  python3 upload_social.py --facebook-only
  python3 upload_social.py --instagram-only
  python3 upload_social.py --tiktok-only
  python3 upload_social.py --setup              # set up Facebook + Instagram (all channels)
  python3 upload_social.py --setup-facebook
  python3 upload_social.py --setup-instagram
  python3 upload_social.py --setup-tiktok
"""

import argparse
import sys

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
    description="Upload all pending content across all channels"
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
parser.add_argument("--limit",            type=int, default=0, help="Upload only this many items per channel")
args = parser.parse_args()

# ─── Channel configs ──────────────────────────────────────────────────────────

CREDS_FILE = "meta_app_credentials.json"

CHANNELS = [
    {
        "label":          "📚 Books Pages and Rain — Videos",
        "profile":        "books-pages-and-rain",
        "csv":            "videos_books_pages_and_rain.csv",
        "folder":         "videos_books_pages_and_rain",
        "results":        "upload_results_social_books-pages-and-rain.csv",
        "tt_results":     "upload_results_tiktok_books-pages-and-rain.csv",
        "yt_results":     "upload_results.csv",
        "photos":         False,
    },
    {
        "label":          "💃 Daisy and the Dance Team — Videos",
        "profile":        "daisy-and-the-dance-team",
        "csv":            "videos_daisy_and_the_dance_team.csv",
        "folder":         "videos_daisy_and_the_dance_team",
        "results":        "upload_results_social_daisy-and-the-dance-team.csv",
        "tt_results":     "upload_results_tiktok_daisy-and-the-dance-team.csv",
        "yt_results":     "upload_results_yt_daisy-and-the-dance-team.csv",
        "photos":         False,
    },
    {
        "label":          "💃 Daisy and the Dance Team — Photos",
        "profile":        "daisy-and-the-dance-team",
        "csv":            "photos_daisy_and_the_dance_team - videos_books_pages_and_rain.csv",
        "folder":         "photos_daisy_and_the_dance_team",
        "results":        "upload_results_social_photos_daisy-and-the-dance-team.csv",
        "tt_results":     "upload_results_tiktok_photos_daisy-and-the-dance-team.csv",
        "yt_results":     "",
        "photos":         True,
    },
]

# ─── Setup ────────────────────────────────────────────────────────────────────

# Run setup once per unique profile
if args.setup or args.setup_facebook or args.setup_instagram or args.setup_tiktok:
    seen = set()
    for ch in CHANNELS:
        p = ch["profile"]
        if p in seen:
            continue
        seen.add(p)
        fb_token = f"token_fb_{p}.json"
        ig_token = f"token_ig_{p}.json"
        tt_token = f"token_tt_{p}.json"
        print(f"\n{'═'*60}\n  Setting up: {p}\n{'═'*60}")
        if args.setup or args.setup_facebook:
            setup_facebook(CREDS_FILE, fb_token)
        if args.setup or args.setup_instagram:
            setup_instagram(CREDS_FILE, ig_token)
        if args.setup_tiktok:
            setup_tiktok(CREDS_FILE, tt_token)
    sys.exit(0)

# ─── Run all channels ─────────────────────────────────────────────────────────

for ch in CHANNELS:
    p = ch["profile"]
    print(f"\n{'█'*60}")
    print(f"  {ch['label']}")
    print(f"{'█'*60}\n")

    run_upload_batch(
        creds_file      = CREDS_FILE,
        fb_token_file   = f"token_fb_{p}.json",
        ig_token_file   = f"token_ig_{p}.json",
        tt_token_file   = f"token_tt_{p}.json",
        csv_file        = ch["csv"],
        videos_folder   = ch["folder"],
        results_file    = ch["results"],
        tt_results_file = ch["tt_results"],
        dry_run         = args.dry_run,
        facebook_only   = args.facebook_only,
        instagram_only  = args.instagram_only,
        youtube_only    = args.youtube_only if not ch["photos"] else False,
        tiktok_only     = args.tiktok_only,
        yt_profile      = p if not ch["photos"] else "",
        yt_results_file = ch["yt_results"],
        limit           = args.limit,
    )
