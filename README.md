# content_hub

A multi-platform uploader that posts **videos and photos** to YouTube, Facebook, Instagram, and TikTok in one command — driven by a CSV file for metadata.

Built for managing multiple channels across all platforms without manual uploading.

---

## Features

- Upload **videos** to YouTube, Facebook, Instagram, and TikTok
- Upload **photos** to Facebook, Instagram, and TikTok
- Automatically detects whether a file is a video or photo based on its extension
- CSV-driven metadata: titles, descriptions, tags, privacy, scheduled publishing
- Automatically skips already-uploaded content (safe to re-run anytime)
- Stamps ✅ in the CSV after each successful upload per platform
- Supports multiple channels — runs all in one command
- `--limit N` flag for test runs
- Per-platform flags: `--youtube-only`, `--facebook-only`, `--instagram-only`, `--tiktok-only`

---

## Usage

```bash
python3 upload_social.py                  # upload everything across all channels
python3 upload_social.py --dry-run        # validate without uploading
python3 upload_social.py --limit 3        # upload only 3 items per channel
python3 upload_social.py --youtube-only   # YouTube only
python3 upload_social.py --facebook-only  # Facebook only
python3 upload_social.py --setup          # set up Facebook + Instagram tokens
python3 upload_social.py --setup-tiktok   # set up TikTok token
```

---

## CSV Format — Videos

| Column | Required | Notes |
|---|---|---|
| `file` | ✅ | Filename inside the videos folder |
| `title` | ✅ | Video title |
| `description` | optional | Video description |
| `social_media_description` | optional | Caption for Facebook, Instagram, TikTok |
| `tags` | optional | Comma-separated |
| `category` | optional | YouTube category name or ID |
| `privacy` | optional | `public`, `private`, or `unlisted` |
| `schedule_time` | optional | `2026-06-01T10:00:00Z` or `2026-06-01 10:00:00 EDT` — leave blank to post immediately |

## CSV Format — Photos

| Column | Required | Notes |
|---|---|---|
| `file` | ✅ | Filename without extension (`.jpeg` added automatically) |
| `social_media_description` | optional | Caption for all platforms |
| `privacy` | optional | `public`, `private`, or `unlisted` |
| `schedule_time` | optional | Same format as videos — leave blank to post immediately |

> **Instagram note:** photos are uploaded to Facebook first, then Facebook's CDN URL is used for Instagram automatically. No extra hosting needed.

---

## Schedule Time Formats

Both UTC and US timezones are supported:

```
2026-06-16T10:00:00Z          # UTC
2026-06-16 02:30:00 EDT       # New York summer time
2026-06-16 02:30:00 EST       # New York winter time
```

Leave `schedule_time` blank to post at the time of running.

---

## Dependencies

```bash
pip install google-auth google-auth-oauthlib google-api-python-client tqdm requests
```
