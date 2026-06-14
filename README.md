# content_hub

A multi-platform video uploader that posts to YouTube, Facebook, Instagram, and TikTok in one command — driven by a CSV file for metadata.

Built for managing a channel across all platforms without manual uploading.

---

## Features

- Upload to YouTube, Facebook, Instagram, and TikTok from a single script
- CSV-driven metadata: titles, descriptions, tags, categories, privacy, scheduled publishing
- Automatically skips already-uploaded videos (safe to re-run anytime)
- Stamps ✅ in the CSV after each successful upload per platform
- `--limit N` flag for test runs
- Per-platform flags: `--youtube-only`, `--facebook-only`, `--instagram-only`, `--tiktok-only`

---

## Usage

```bash
python3 upload_social.py                  # upload to all platforms
python3 upload_social.py --dry-run        # validate without uploading
python3 upload_social.py --limit 3        # upload only 3 videos
python3 upload_social.py --youtube-only   # YouTube only
python3 upload_social.py --facebook-only  # Facebook only
python3 upload_social.py --setup          # set up Facebook + Instagram tokens
python3 upload_social.py --setup-tiktok   # set up TikTok token
```

---

## CSV Format

| Column | Required | Notes |
|---|---|---|
| `file` | ✅ | Filename inside the videos folder |
| `title` | ✅ | Video title |
| `description` | optional | Video description |
| `tags` | optional | Comma-separated |
| `category` | optional | YouTube category name or ID |
| `privacy` | optional | `public`, `private`, or `unlisted` |
| `schedule_time` | optional | ISO 8601 UTC: `2026-06-01T10:00:00Z` |

---

## Dependencies

```bash
pip install google-auth google-auth-oauthlib google-api-python-client tqdm requests
```
