"""
social_uploader.py — Combined YouTube + Facebook + Instagram + TikTok upload engine.

Posts the same video to all four platforms in one run.

Setup commands:
  python3 upload_social.py --setup              # set up Facebook + Instagram
  python3 upload_social.py --setup-facebook     # set up Facebook only
  python3 upload_social.py --setup-instagram    # set up Instagram only
  python3 upload_social.py --setup-tiktok       # set up TikTok only
  (YouTube authenticates automatically on first run — opens browser)

Run commands:
  python3 upload_social.py                      # upload to all platforms
  python3 upload_social.py --dry-run            # validate without uploading
  python3 upload_social.py --youtube-only       # YouTube only
  python3 upload_social.py --facebook-only      # Facebook only
  python3 upload_social.py --instagram-only     # Instagram only
  python3 upload_social.py --tiktok-only        # TikTok only
  python3 upload_social.py --limit 3            # upload only 3 videos
"""

import csv
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from tqdm import tqdm

# ─── YouTube engine (inlined) ─────────────────────────────────────────────────
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False

YT_SCOPES             = ["https://www.googleapis.com/auth/youtube.upload"]
YT_CLIENT_SECRETS     = "client_secrets.json"
YT_TOKEN_TEMPLATE     = "token_{profile}.json"
YT_RETRIABLE_CODES    = [500, 502, 503, 504]
YT_CATEGORY_IDS = {
    "Film & Animation": "1", "Autos & Vehicles": "2", "Music": "10",
    "Pets & Animals": "15", "Sports": "17", "Travel & Events": "19",
    "Gaming": "20", "People & Blogs": "22", "Comedy": "23",
    "Entertainment": "24", "News & Politics": "25", "Howto & Style": "26",
    "Education": "27", "Science & Technology": "28", "Nonprofits & Activism": "29",
}


def parse_tags(raw: str) -> list:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def resolve_category(value: str) -> str:
    if not value:
        return "22"
    if value.isdigit():
        return value
    for name, cid in YT_CATEGORY_IDS.items():
        if name.lower() == value.lower():
            return cid
    return "22"


def yt_authenticate(profile: str = "default"):
    token_file = YT_TOKEN_TEMPLATE.format(profile=profile)
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, YT_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(YT_CLIENT_SECRETS):
                print(f"\n❌  '{YT_CLIENT_SECRETS}' not found.")
                print("    Download from: https://console.cloud.google.com/apis/credentials\n")
                sys.exit(1)
            print(f"\n🌐  Opening browser to sign in for profile '{profile}' …\n")
            flow  = InstalledAppFlow.from_client_secrets_file(YT_CLIENT_SECRETS, YT_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as f:
            f.write(creds.to_json())
        print(f"✅  Credentials saved to {token_file}\n")
    return build("youtube", "v3", credentials=creds)


def yt_upload_video(youtube, video_path: str, title: str, description: str,
                     tags: list, category_id: str, privacy: str,
                     publish_at: str = None) -> str:
    snippet = {
        "title":       title[:100],
        "description": description[:5000],
        "tags":        tags,
        "categoryId":  category_id,
    }
    status = {"privacyStatus": privacy}
    if publish_at:
        status["privacyStatus"]            = "private"
        status["publishAt"]                = publish_at
        status["selfDeclaredMadeForKids"]  = False

    media   = MediaFileUpload(video_path, chunksize=1024*1024, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body={"snippet": snippet, "status": status},
        media_body=media,
    )

    response = error = None
    retry    = 0
    with tqdm(total=100, desc=f"  ↑ {os.path.basename(video_path)}",
              unit="%", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}%") as pbar:
        prev = 0
        while response is None:
            try:
                status_obj, response = request.next_chunk()
                if status_obj:
                    p = int(status_obj.progress() * 100)
                    pbar.update(p - prev)
                    prev = p
            except HttpError as e:
                if e.resp.status in YT_RETRIABLE_CODES:
                    error = str(e)
                else:
                    raise
            except Exception as e:
                error = str(e)
            if error:
                retry += 1
                if retry > MAX_RETRIES:
                    raise RuntimeError(f"YouTube max retries exceeded: {error}")
                wait = 2 ** retry
                print(f"\n  ⚠️  Retry {retry}/{MAX_RETRIES} in {wait}s")
                time.sleep(wait)
                error = None
        pbar.update(100 - prev)

    return response.get("id", "")

# ─── Constants ────────────────────────────────────────────────────────────────

API_VERSION   = "v21.0"
FB_BASE       = f"https://graph.facebook.com/{API_VERSION}"
FB_VIDEO_BASE = f"https://graph-video.facebook.com/{API_VERSION}"
IG_BASE       = f"https://graph.instagram.com/{API_VERSION}"

TT_BASE       = "https://open.tiktokapis.com/v2"
TT_AUTH_URL   = "https://www.tiktok.com/v2/auth/authorize/"
TT_TOKEN_URL  = f"{TT_BASE}/oauth/token/"

CHUNK_SIZE              = 10 * 1024 * 1024
MAX_RETRIES             = 10
RETRY_BASE_DELAY        = 5
CONTAINER_POLL_INTERVAL = 5
CONTAINER_POLL_TIMEOUT  = 300


# ══════════════════════════════════════════════════════════════════════════════
#  FACEBOOK SETUP
# ══════════════════════════════════════════════════════════════════════════════

def setup_facebook(creds_file: str, fb_token_file: str):
    print("\n" + "═" * 60)
    print("  Facebook Page Setup")
    print("═" * 60)

    # App credentials
    if Path(creds_file).exists():
        with open(creds_file) as f:
            creds = json.load(f)
        app_id, app_secret = creds["app_id"], creds["app_secret"]
        print(f"\n✅  Using existing credentials from {creds_file}")
    else:
        print("""
Step 1: Meta App credentials
─────────────────────────────
developers.facebook.com/apps → your app → App Settings → Basic
""")
        app_id     = input("Enter App ID: ").strip()
        app_secret = input("Enter App Secret: ").strip()
        with open(creds_file, "w") as f:
            json.dump({"app_id": app_id, "app_secret": app_secret}, f, indent=2)
        print(f"✅  Saved to {creds_file}")

    # Short-lived user token
    print("""
Step 2: Generate a User Access Token
──────────────────────────────────────
  1. Go to https://developers.facebook.com/tools/explorer/
  2. Make sure the top dropdown shows graph.facebook.com
  3. Select your app
  4. Click "Get User Access Token"
  5. Check: pages_show_list, pages_read_engagement, pages_manage_posts
  6. Generate and copy the token
""")
    short_token = input("Paste User Access Token: ").strip()

    # Exchange for long-lived token
    print("\nExchanging for long-lived token...")
    resp = requests.get(
        f"{FB_BASE}/oauth/access_token",
        params={
            "grant_type":        "fb_exchange_token",
            "client_id":         app_id,
            "client_secret":     app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"❌  Failed: {resp.text}")
        sys.exit(1)
    long_user_token = resp.json()["access_token"]
    print("✅  Long-lived user token obtained.")

    # Find Pages
    print("\nLooking for your Facebook Pages...")
    pages_resp = requests.get(
        f"{FB_BASE}/me/accounts",
        params={"access_token": long_user_token},
        timeout=30,
    )
    pages = pages_resp.json().get("data", [])

    if not pages:
        print("  ⚠  No Pages found automatically.")
        print("""
  Find your Page ID manually:
    Meta Business Suite → Settings → Business Info → Pages
    OR: go to your Page → About → scroll to bottom for Page ID
""")
        page_id   = input("Enter your Page ID: ").strip()
        page_name = input("Enter your Page name (for display): ").strip()
    else:
        print(f"\n  Found {len(pages)} Page(s):")
        for i, p in enumerate(pages):
            print(f"    [{i+1}] {p['name']}  (ID: {p['id']})")
        choice = 0
        while choice < 1 or choice > len(pages):
            try:
                choice = int(input(f"\nSelect a page (1–{len(pages)}): "))
            except ValueError:
                pass
        page_id   = pages[choice - 1]["id"]
        page_name = pages[choice - 1]["name"]

    # Get permanent Page Access Token
    print(f"\nGetting Page Access Token for '{page_name}'...")
    page_resp = requests.get(
        f"{FB_BASE}/{page_id}",
        params={"fields": "access_token,name", "access_token": long_user_token},
        timeout=30,
    )
    page_data = page_resp.json()
    if "access_token" not in page_data:
        print(f"❌  Could not get Page token: {page_data}")
        sys.exit(1)

    token_data = {
        "page_access_token": page_data["access_token"],
        "page_id":           page_id,
        "page_name":         page_name,
        "obtained_at":       datetime.now(timezone.utc).isoformat(),
    }
    with open(fb_token_file, "w") as f:
        json.dump(token_data, f, indent=2)
    print(f"✅  Saved to {fb_token_file}")

    print(f"""
═══════════════════════════════════════════════════════════════
  Facebook setup complete: {page_name}
═══════════════════════════════════════════════════════════════
""")


# ══════════════════════════════════════════════════════════════════════════════
#  INSTAGRAM SETUP
# ══════════════════════════════════════════════════════════════════════════════

def setup_instagram(creds_file: str, ig_token_file: str):
    print("\n" + "═" * 60)
    print("  Instagram Setup")
    print("═" * 60)

    # App credentials
    if Path(creds_file).exists():
        with open(creds_file) as f:
            creds = json.load(f)
        app_id, app_secret = creds["app_id"], creds["app_secret"]
        print(f"\n✅  Using existing credentials from {creds_file}")
    else:
        print("\nStep 1: Meta App ID and Secret")
        app_id     = input("Enter App ID: ").strip()
        app_secret = input("Enter App Secret: ").strip()
        with open(creds_file, "w") as f:
            json.dump({"app_id": app_id, "app_secret": app_secret}, f, indent=2)
        print(f"✅  Saved to {creds_file}")

    # Short-lived user token with Instagram permissions
    print("""
Step 2: Generate a User Access Token with Instagram permissions
────────────────────────────────────────────────────────────────
  1. Go to https://developers.facebook.com/tools/explorer/
  2. Make sure the top dropdown shows graph.facebook.com
  3. Select your app
  4. Click "Get User Access Token"
  5. Check these permissions:
       instagram_business_basic
       instagram_business_content_publish
  6. Generate and copy the token

  If those permissions don't appear in the list:
    → Go to your app → App Review → Permissions and Features
    → Search for each one and click Add
    → Come back to Explorer and refresh
""")
    short_token = input("Paste User Access Token: ").strip()

    # Exchange for long-lived token
    print("\nExchanging for long-lived token...")
    resp = requests.get(
        f"{FB_BASE}/oauth/access_token",
        params={
            "grant_type":        "fb_exchange_token",
            "client_id":         app_id,
            "client_secret":     app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"❌  Failed: {resp.text}")
        sys.exit(1)
    long_token = resp.json()["access_token"]
    print("✅  Long-lived token obtained.")

    # Get Instagram user — try graph.instagram.com first, fallback to graph.facebook.com
    print("\nFetching your Instagram account...")
    ig_user_id = ig_username = ""

    ig_resp = requests.get(
        f"{IG_BASE}/me",
        params={"fields": "id,username", "access_token": long_token},
        timeout=30,
    )
    if ig_resp.status_code == 200 and "id" in ig_resp.json():
        ig_data    = ig_resp.json()
        ig_user_id = ig_data["id"]
        ig_username = ig_data.get("username", ig_user_id)
    else:
        # Fallback: via Facebook Graph API
        fb_ig_resp = requests.get(
            f"{FB_BASE}/me",
            params={
                "fields":       "instagram_accounts{id,username}",
                "access_token": long_token,
            },
            timeout=30,
        )
        ig_accounts = (fb_ig_resp.json()
                       .get("instagram_accounts", {})
                       .get("data", []))
        if ig_accounts:
            ig_user_id  = ig_accounts[0]["id"]
            ig_username = ig_accounts[0].get("username", ig_user_id)

    if not ig_user_id:
        print("""
  ⚠️  Could not find your Instagram account automatically.

  This can happen when the token doesn't include instagram_business_basic,
  or when the Instagram account isn't linked via Business Manager.

  You can enter your Instagram details manually instead:
    • Instagram User ID: find it in Meta Business Suite → Settings
      → Accounts → Instagram accounts → click your account
    • Or visit: https://www.instagram.com/[yourusername]/?__a=1&__d=dis
      and look for "id" (must be logged in)
""")
        manual = input("Enter manually? (y/n): ").strip().lower()
        if manual == "y":
            ig_user_id  = input("Instagram User ID (numbers only): ").strip()
            ig_username = input("Instagram username (without @): ").strip()
        else:
            print("❌  Setup cancelled.")
            sys.exit(1)

    print(f"✅  Instagram account: @{ig_username}  (ID: {ig_user_id})")

    token_data = {
        "access_token": long_token,
        "ig_user_id":   ig_user_id,
        "ig_username":  ig_username,
        "obtained_at":  datetime.now(timezone.utc).isoformat(),
    }
    with open(ig_token_file, "w") as f:
        json.dump(token_data, f, indent=2)
    print(f"✅  Saved to {ig_token_file}")

    print(f"""
═══════════════════════════════════════════════════════════════
  Instagram setup complete: @{ig_username}
  Note: Token lasts 60 days. Re-run --setup-instagram to refresh.
═══════════════════════════════════════════════════════════════
""")


# ══════════════════════════════════════════════════════════════════════════════
#  TIKTOK SETUP
# ══════════════════════════════════════════════════════════════════════════════

def setup_tiktok(creds_file: str, tt_token_file: str):
    print("\n" + "═" * 60)
    print("  TikTok Setup")
    print("═" * 60)

    # App credentials
    if Path(creds_file).exists():
        with open(creds_file) as f:
            creds = json.load(f)
        if "tt_client_key" in creds:
            client_key    = creds["tt_client_key"]
            client_secret = creds["tt_client_secret"]
            print(f"\n✅  Using existing TikTok credentials from {creds_file}")
        else:
            client_key = client_secret = ""
    else:
        client_key = client_secret = ""

    if not client_key:
        print("""
Step 1: TikTok Developer credentials
──────────────────────────────────────
  1. Go to https://developers.tiktok.com/
  2. My Apps → your app → Manage
  3. Copy Client Key and Client Secret
""")
        client_key    = input("Enter Client Key: ").strip()
        client_secret = input("Enter Client Secret: ").strip()

        # Merge into existing creds file if it exists
        existing = {}
        if Path(creds_file).exists():
            with open(creds_file) as f:
                existing = json.load(f)
        existing["tt_client_key"]    = client_key
        existing["tt_client_secret"] = client_secret
        with open(creds_file, "w") as f:
            json.dump(existing, f, indent=2)
        print(f"✅  Saved to {creds_file}")

    redirect_uri = "https://localhost/callback"
    scope        = "video.publish,video.upload"

    import urllib.parse, webbrowser, secrets
    state     = secrets.token_hex(8)
    auth_url  = (
        f"{TT_AUTH_URL}?client_key={client_key}"
        f"&scope={urllib.parse.quote(scope)}"
        f"&response_type=code"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&state={state}"
    )

    print(f"""
Step 2: Authorise your TikTok account
───────────────────────────────────────
  Opening browser... if it doesn't open, copy this URL manually:

  {auth_url}

  After you approve, the browser will redirect to a localhost URL that
  shows an error — that's fine. Copy the FULL URL from the address bar
  and paste it below.
""")
    webbrowser.open(auth_url)
    callback_url = input("Paste the full redirect URL here: ").strip()

    # Extract code from callback URL
    parsed = urllib.parse.urlparse(callback_url)
    params = urllib.parse.parse_qs(parsed.query)
    code   = params.get("code", [""])[0]
    if not code:
        print("❌  Could not extract code from URL. Make sure you pasted the full redirect URL.")
        sys.exit(1)

    # Exchange code for token
    print("\nExchanging for access token...")
    resp = requests.post(
        TT_TOKEN_URL,
        data={
            "client_key":     client_key,
            "client_secret":  client_secret,
            "code":           code,
            "grant_type":     "authorization_code",
            "redirect_uri":   redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if not resp.ok:
        print(f"❌  Token exchange failed: {resp.text}")
        sys.exit(1)

    data = resp.json()
    if "access_token" not in data:
        print(f"❌  Unexpected response: {data}")
        sys.exit(1)

    import time as _time
    token_data = {
        "access_token":  data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "open_id":       data.get("open_id", ""),
        "expires_at":    int(_time.time()) + int(data.get("expires_in", 86400)),
        "obtained_at":   datetime.now(timezone.utc).isoformat(),
    }
    with open(tt_token_file, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"✅  TikTok token saved to {tt_token_file}")
    print(f"""
═══════════════════════════════════════════════════════════════
  TikTok setup complete!
  Note: Access token lasts 24 hours. Refresh token lasts 1 year.
  Re-run --setup-tiktok to refresh if needed.
═══════════════════════════════════════════════════════════════
""")


def _refresh_tiktok_token(creds_file: str, tt_token_file: str) -> dict:
    """Refresh TikTok token if expired. Returns current token data."""
    import time as _time
    with open(tt_token_file) as f:
        token_data = json.load(f)

    # If token is still valid (with 5-min buffer), return as-is
    if int(token_data.get("expires_at", 0)) > _time.time() + 300:
        return token_data

    print("  🔄  TikTok token expired — refreshing...")
    with open(creds_file) as f:
        creds = json.load(f)

    resp = requests.post(
        TT_TOKEN_URL,
        data={
            "client_key":     creds["tt_client_key"],
            "client_secret":  creds["tt_client_secret"],
            "grant_type":     "refresh_token",
            "refresh_token":  token_data["refresh_token"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"TikTok token refresh failed: {resp.text}")

    data = resp.json()
    token_data["access_token"] = data["access_token"]
    token_data["expires_at"]   = int(_time.time()) + int(data.get("expires_in", 86400))
    if data.get("refresh_token"):
        token_data["refresh_token"] = data["refresh_token"]
    with open(tt_token_file, "w") as f:
        json.dump(token_data, f, indent=2)
    print("  ✅  Token refreshed.")
    return token_data


# ══════════════════════════════════════════════════════════════════════════════
#  TIKTOK UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def upload_to_tiktok(access_token: str, open_id: str,
                      video_path: str, metadata: dict) -> str:
    file_size  = os.path.getsize(video_path)
    chunk_size = CHUNK_SIZE
    num_chunks = math.ceil(file_size / chunk_size)

    caption = (metadata.get("social_media_description", "").strip()
               or metadata.get("description", "").strip()
               or metadata.get("title", ""))[:2200]

    privacy_map = {
        "public":   "PUBLIC_TO_EVERYONE",
        "private":  "SELF_ONLY",
        "unlisted": "FOLLOWER_OF_CREATOR",
    }
    privacy = privacy_map.get(
        metadata.get("privacy", "public").lower(), "PUBLIC_TO_EVERYONE"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json; charset=UTF-8",
    }

    # Init upload
    init_resp = requests.post(
        f"{TT_BASE}/post/publish/video/init/",
        json={
            "post_info": {
                "title":                    caption,
                "privacy_level":            privacy,
                "disable_duet":             False,
                "disable_comment":          False,
                "disable_stitch":           False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": {
                "source":            "FILE_UPLOAD",
                "video_size":        file_size,
                "chunk_size":        min(chunk_size, file_size),
                "total_chunk_count": num_chunks,
            },
        },
        headers=headers,
        timeout=60,
    )
    if not init_resp.ok:
        raise RuntimeError(f"TikTok init failed ({init_resp.status_code}): {init_resp.text}")

    init_data  = init_resp.json().get("data", {})
    publish_id = init_data.get("publish_id")
    upload_url = init_data.get("upload_url")
    if not publish_id or not upload_url:
        raise RuntimeError(f"TikTok init missing publish_id/upload_url: {init_resp.text}")

    # Upload chunks
    with open(video_path, "rb") as f:
        with tqdm(total=file_size, unit="B", unit_scale=True,
                  desc="    TT upload", leave=False) as pbar:
            for chunk_idx in range(num_chunks):
                offset = chunk_idx * chunk_size
                chunk  = f.read(chunk_size)
                end    = offset + len(chunk) - 1

                for attempt in range(MAX_RETRIES):
                    try:
                        r = requests.put(
                            upload_url,
                            headers={
                                "Content-Range":  f"bytes {offset}-{end}/{file_size}",
                                "Content-Length": str(len(chunk)),
                                "Content-Type":   "video/mp4",
                            },
                            data=chunk,
                            timeout=300,
                        )
                        r.raise_for_status()
                        pbar.update(len(chunk))
                        break
                    except Exception as e:
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                        else:
                            raise RuntimeError(f"TikTok chunk {chunk_idx} failed: {e}")

    # Poll for status
    print("    ⏳ Processing...", end="", flush=True)
    elapsed = 0
    while elapsed < CONTAINER_POLL_TIMEOUT:
        sr = requests.post(
            f"{TT_BASE}/post/publish/status/fetch/",
            json={"publish_id": publish_id},
            headers=headers,
            timeout=30,
        )
        if sr.ok:
            status = sr.json().get("data", {}).get("status", "")
            if status == "PUBLISH_COMPLETE":
                print(" done.")
                return publish_id
            elif status in ("FAILED", "PUBLISH_FAILED"):
                raise RuntimeError(f"TikTok publish failed: {sr.text}")
        print(".", end="", flush=True)
        time.sleep(CONTAINER_POLL_INTERVAL)
        elapsed += CONTAINER_POLL_INTERVAL
    else:
        raise TimeoutError("TikTok upload timed out.")


def load_tt_done(tt_results_file: str) -> set:
    """Files already successfully uploaded to TikTok."""
    done = set()
    if not Path(tt_results_file).exists():
        return done
    with open(tt_results_file, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("tt_publish_id", "").strip():
                done.add(row.get("file", "").strip())
    return done


# ══════════════════════════════════════════════════════════════════════════════
#  FACEBOOK UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def upload_to_facebook(page_id: str, page_token: str, app_id: str,
                        video_path: str, metadata: dict) -> str:
    """
    Upload a video to a Facebook Page using direct multipart upload.
    Simple and reliable for short-form video content.
    """
    file_size = os.path.getsize(video_path)
    file_name = os.path.basename(video_path)

    desc = (metadata.get("social_media_description", "").strip()
            or metadata.get("description", "").strip())

    schedule_time = metadata.get("schedule_time", "").strip()

    fields: dict = {
        "access_token": page_token,
        "title":        metadata.get("title", ""),
    }
    if desc:
        fields["description"] = desc

    if schedule_time:
        ts = _parse_schedule_time(schedule_time)
        if ts <= int(time.time()) + 600:
            raise ValueError("schedule_time must be at least 10 min in the future")
        fields["published"]                = "false"
        fields["unpublished_content_type"] = "SCHEDULED"
        fields["scheduled_publish_time"]   = str(ts)
    else:
        fields["published"] = "true"

    print(f"    Uploading {file_name} ({file_size / 1024 / 1024:.1f} MB)...")

    for attempt in range(MAX_RETRIES):
        try:
            with open(video_path, "rb") as f:
                resp = requests.post(
                    f"{FB_VIDEO_BASE}/{page_id}/videos",
                    data=fields,
                    files={"source": (file_name, f, "video/mp4")},
                    timeout=600,
                )
            if not resp.ok:
                raise RuntimeError(f"FB publish failed ({resp.status_code}): {resp.text}")
            data = resp.json()
            if "id" not in data:
                raise RuntimeError(f"FB publish returned no ID: {data}")
            return data["id"]
        except RuntimeError:
            raise
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BASE_DELAY * (2 ** attempt)
                print(f"    Retry {attempt + 1}/{MAX_RETRIES} in {wait}s ({e})")
                time.sleep(wait)
            else:
                raise RuntimeError(f"FB upload failed after {MAX_RETRIES} attempts: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  INSTAGRAM UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def upload_to_instagram(ig_user_id: str, ig_token: str,
                         video_path: str, metadata: dict) -> str:
    """
    Upload a video to Instagram via the Facebook Graph API.
    Uses graph.facebook.com (not graph.instagram.com) because we hold
    a Facebook User Access Token with instagram_business_content_publish.
    """
    caption    = (metadata.get("social_media_description", "").strip()
                  or metadata.get("description", "").strip()
                  or metadata.get("title", ""))
    media_type    = metadata.get("media_type", "REELS").strip().upper() or "REELS"
    schedule_time = metadata.get("schedule_time", "").strip()

    params: dict = {
        "access_token": ig_token,
        "media_type":   media_type,
        "upload_type":  "resumable",
        "caption":      caption,
    }
    if schedule_time:
        ts = _parse_schedule_time(schedule_time)
        if ts <= int(time.time()) + 600:
            raise ValueError("schedule_time must be at least 10 min in the future")
        params["published"]              = "false"
        params["scheduled_publish_time"] = str(ts)

    # Use graph.facebook.com — Facebook tokens are not accepted by graph.instagram.com
    init_resp = requests.post(
        f"{FB_BASE}/{ig_user_id}/media",
        params=params,
        timeout=60,
    )
    if not init_resp.ok:
        raise RuntimeError(f"IG container init failed ({init_resp.status_code}): {init_resp.text}")
    init_data = init_resp.json()
    if "id" not in init_data or "uri" not in init_data:
        raise RuntimeError(f"IG container init failed: {init_data}")
    creation_id = init_data["id"]
    upload_url  = init_data["uri"]

    file_size = os.path.getsize(video_path)
    offset    = 0
    with open(video_path, "rb") as f:
        with tqdm(total=file_size, unit="B", unit_scale=True,
                  desc="    IG upload", leave=False) as pbar:
            while offset < file_size:
                chunk      = f.read(CHUNK_SIZE)
                end_offset = offset + len(chunk) - 1
                for attempt in range(MAX_RETRIES):
                    try:
                        r = requests.post(
                            upload_url,
                            headers={
                                "Authorization": f"OAuth {ig_token}",
                                "offset":        str(offset),
                                "file_size":     str(file_size),
                            },
                            data=chunk,
                            timeout=300,
                        )
                        r.raise_for_status()
                        pbar.update(len(chunk))
                        offset = end_offset + 1
                        break
                    except Exception as e:
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                        else:
                            raise RuntimeError(f"IG chunk failed: {e}")

    print("    ⏳ Processing...", end="", flush=True)
    elapsed = 0
    while elapsed < CONTAINER_POLL_TIMEOUT:
        sr = requests.get(
            f"{FB_BASE}/{creation_id}",
            params={"fields": "status_code,status", "access_token": ig_token},
            timeout=30,
        )
        sr.raise_for_status()
        status_code = sr.json().get("status_code", "")
        if status_code == "FINISHED":
            print(" ready.")
            break
        elif status_code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"IG container failed: {status_code}")
        print(".", end="", flush=True)
        time.sleep(CONTAINER_POLL_INTERVAL)
        elapsed += CONTAINER_POLL_INTERVAL
    else:
        raise TimeoutError("IG container timed out.")

    if schedule_time:
        return creation_id

    pub_resp = requests.post(
        f"{FB_BASE}/{ig_user_id}/media_publish",
        params={"creation_id": creation_id, "access_token": ig_token},
        timeout=60,
    )
    if not pub_resp.ok:
        raise RuntimeError(f"IG publish failed ({pub_resp.status_code}): {pub_resp.text}")
    data = pub_resp.json()
    if "id" not in data:
        raise RuntimeError(f"IG publish returned no ID: {data}")
    return data["id"]


# ══════════════════════════════════════════════════════════════════════════════
#  SHARED
# ══════════════════════════════════════════════════════════════════════════════

def _parse_schedule_time(s: str) -> int:
    import re
    s = s.replace("Z", "+00:00")
    s = re.sub(r'T(\d):', r'T0\1:', s)   # pad single-digit hour: T5: → T05:
    dt = datetime.fromisoformat(s)
    return int(dt.timestamp())


def _normalize_schedule_time(s: str) -> str:
    """If schedule_time is in the past, bump it to 1 day ahead (same time).
    Returns the original string if it's still in the future, or empty."""
    if not s:
        return s
    import re
    now = datetime.now(timezone.utc)
    _s  = re.sub(r'T(\d):', r'T0\1:', s.replace("Z", "+00:00"))
    dt  = datetime.fromisoformat(_s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if dt > now:
        return s
    from datetime import timedelta
    bumped = datetime.now(timezone.utc).replace(
        hour=dt.hour, minute=dt.minute, second=dt.second, microsecond=0
    ) + timedelta(days=1)
    bumped_str = bumped.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"  ⏰  schedule_time was in the past — bumped to {bumped_str}")
    return bumped_str


def load_yt_done(yt_results_file: str) -> set:
    """Files already successfully uploaded to YouTube."""
    done = set()
    if not Path(yt_results_file).exists():
        return done
    with open(yt_results_file, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "success":
                done.add(row.get("file", "").strip())
    return done


def load_fb_done(results_file: str) -> set:
    """Files already successfully uploaded to Facebook."""
    done = set()
    if not Path(results_file).exists():
        return done
    with open(results_file, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("fb_video_id", "").strip():
                done.add(row.get("file", "").strip())
    return done


def load_ig_done(results_file: str) -> set:
    """Files already successfully uploaded to Instagram."""
    done = set()
    if not Path(results_file).exists():
        return done
    with open(results_file, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("ig_media_id", "").strip():
                done.add(row.get("file", "").strip())
    return done


def log_result(results_file: str, row: dict):
    path       = Path(results_file)
    fieldnames = ["file", "title", "fb_video_id", "ig_media_id",
                  "status", "error", "uploaded_at"]
    write_header = not path.exists() or path.stat().st_size == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN BATCH RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_upload_batch(
    creds_file:      str,
    fb_token_file:   str,
    ig_token_file:   str,
    tt_token_file:   str,
    csv_file:        str,
    videos_folder:   str,
    results_file:    str,
    tt_results_file: str  = "upload_results_tiktok.csv",
    dry_run:         bool = False,
    facebook_only:   bool = False,
    instagram_only:  bool = False,
    youtube_only:    bool = False,
    tiktok_only:     bool = False,
    yt_profile:      str  = "",
    yt_results_file: str  = "upload_results.csv",
    limit:           int  = 0,
):
    # Which platforms are enabled
    only_one = any([facebook_only, instagram_only, youtube_only, tiktok_only])
    post_to_yt = youtube_only  or (not only_one)
    post_to_fb = facebook_only or (not only_one)
    post_to_ig = instagram_only or (not only_one)
    post_to_tt = tiktok_only   or (not only_one)

    # YouTube
    yt_client = None
    if post_to_yt:
        if not YOUTUBE_AVAILABLE:
            print("❌  youtube_uploader.py not found — YouTube uploads disabled.")
            post_to_yt = False
        elif yt_profile:
            print("🔐  Authenticating YouTube…")
            yt_client = yt_authenticate(yt_profile)
            print("✅  YouTube authenticated.\n")

    # Facebook
    fb_page_id = fb_page_token = fb_app_id = fb_page_name = ""
    fb_ready = post_to_fb and Path(fb_token_file).exists()
    if fb_ready:
        with open(fb_token_file) as f:
            fb_data = json.load(f)
        fb_page_token = fb_data["page_access_token"]
        fb_page_id    = fb_data["page_id"]
        fb_page_name  = fb_data.get("page_name", fb_page_id)
        with open(creds_file) as f:
            fb_app_id = json.load(f)["app_id"]

    # Instagram
    ig_user_id = ig_token = ig_username = ""
    ig_ready = post_to_ig and Path(ig_token_file).exists()
    if ig_ready:
        with open(ig_token_file) as f:
            ig_data = json.load(f)
        ig_token    = ig_data["access_token"]
        ig_user_id  = ig_data["ig_user_id"]
        ig_username = ig_data.get("ig_username", ig_user_id)

    # TikTok
    tt_access_token = tt_open_id = ""
    tt_ready = post_to_tt and Path(tt_token_file).exists()
    if tt_ready:
        try:
            tt_data         = _refresh_tiktok_token(creds_file, tt_token_file)
            tt_access_token = tt_data["access_token"]
            tt_open_id      = tt_data.get("open_id", "")
        except Exception as e:
            print(f"⚠️  TikTok token error: {e}  — skipping TikTok.")
            tt_ready = False

    if not yt_client and not fb_ready and not ig_ready and not tt_ready:
        print("❌  No platforms ready. Run --setup or check token files.\n")
        sys.exit(1)

    print(f"\n{'═' * 60}")
    if yt_client:  print(f"  YouTube:   ✅")
    if fb_ready:   print(f"  Facebook:  {fb_page_name}")
    if ig_ready:   print(f"  Instagram: @{ig_username}")
    if tt_ready:   print(f"  TikTok:    ✅")
    if dry_run:    print("  MODE: DRY RUN")
    print(f"{'═' * 60}\n")

    if not Path(csv_file).exists():
        print(f"❌  CSV not found: {csv_file}\n")
        sys.exit(1)

    with open(csv_file, newline="", encoding="utf-8-sig") as f:
        reader     = csv.DictReader(f)
        csv_fields = list(reader.fieldnames or [])
        all_rows   = list(reader)

    # Ensure platform columns exist in CSV
    for col in ["youtube", "facebook", "instagram", "tiktok"]:
        if col not in csv_fields:
            csv_fields.append(col)
    for r in all_rows:
        r.setdefault("youtube",   "")
        r.setdefault("facebook",  "")
        r.setdefault("instagram", "")
        r.setdefault("tiktok",    "")

    rows_by_file: dict = {r.get("file", "").strip(): r for r in all_rows if r.get("file", "").strip()}

    def save_csv():
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_rows)

    # Per-platform done sets
    yt_done = load_yt_done(yt_results_file)  if yt_client else set()
    fb_done = load_fb_done(results_file)     if fb_ready  else set()
    ig_done = load_ig_done(results_file)     if ig_ready  else set()
    tt_done = load_tt_done(tt_results_file)  if tt_ready  else set()

    def needs_upload(filename: str) -> bool:
        if yt_client and filename not in yt_done: return True
        if fb_ready  and filename not in fb_done: return True
        if ig_ready  and filename not in ig_done: return True
        if tt_ready  and filename not in tt_done: return True
        return False

    eligible  = [r for r in all_rows
                 if r.get("file", "").strip() and needs_upload(r["file"].strip())]
    skipped   = len(all_rows) - len(eligible)
    to_upload = eligible[:limit] if limit > 0 else eligible

    print(f"  CSV rows:   {len(all_rows)}")
    print(f"  Skipped:    {skipped}  (already uploaded)")
    if limit > 0 and len(eligible) > limit:
        print(f"  Limited to: {limit}  (of {len(eligible)} pending)")
    print(f"  To upload:  {len(to_upload)}\n")

    if not to_upload:
        print("✅  Nothing new to upload.\n")
        return

    success = fail = 0

    for i, row in enumerate(to_upload, 1):
        filename   = row["file"].strip()
        title      = row.get("title", filename).strip()
        video_path = os.path.join(videos_folder, filename)

        # Bump past schedule times to tomorrow (same time of day)
        if row.get("schedule_time", "").strip():
            row = dict(row)  # don't mutate the original
            row["schedule_time"] = _normalize_schedule_time(row["schedule_time"].strip())

        print(f"[{i}/{len(to_upload)}] {title}")

        if not os.path.exists(video_path):
            print(f"  ❌  File not found: {video_path}\n")
            log_result(results_file, {
                "file": filename, "title": title,
                "fb_video_id": "", "ig_media_id": "",
                "status": "error", "error": "file not found",
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
            })
            fail += 1
            continue

        if dry_run:
            caption = (row.get("social_media_description", "")
                       or row.get("description", "") or title)
            print(f"  ✔  [DRY RUN] '{filename}'")
            print(f"       caption: {caption[:80]}")
            if yt_client: print(f"       → YouTube")
            if fb_ready:  print(f"       → Facebook:  {fb_page_name}")
            if ig_ready:  print(f"       → Instagram: @{ig_username}")
            if tt_ready:  print(f"       → TikTok")
            print()
            continue

        fb_video_id = ig_media_id = yt_video_id = tt_publish_id = ""
        errors = []

        # ── YouTube ──
        if yt_client and filename not in yt_done:
            print("  🎬 Uploading to YouTube...")
            try:
                yt_video_id = yt_upload_video(
                    yt_client,
                    video_path  = video_path,
                    title       = title,
                    description = row.get("description", ""),
                    tags        = parse_tags(row.get("tags", "")),
                    category_id = resolve_category(row.get("category", "")),
                    privacy     = row.get("privacy", "private").lower(),
                    publish_at  = row.get("schedule_time", "").strip() or None,
                )
                if yt_video_id:
                    print(f"  ✅  YouTube — https://www.youtube.com/watch?v={yt_video_id}")
                    if filename in rows_by_file:
                        rows_by_file[filename]["youtube"] = "✅"
                        save_csv()
                    # Write to YouTube's own results file
                    _log_yt_result(yt_results_file, filename, title, yt_video_id)
                else:
                    raise RuntimeError("No video ID returned")
            except Exception as e:
                print(f"  ❌  YouTube failed: {e}")
                errors.append(f"YT: {e}")

        # ── Facebook ──
        if fb_ready and filename not in fb_done:
            print("  📘 Uploading to Facebook...")
            try:
                fb_video_id = upload_to_facebook(
                    fb_page_id, fb_page_token, fb_app_id, video_path, row)
                print(f"  ✅  Facebook — video ID: {fb_video_id}")
                if filename in rows_by_file:
                    rows_by_file[filename]["facebook"] = "✅"
                    save_csv()
            except Exception as e:
                print(f"  ❌  Facebook failed: {e}")
                errors.append(f"FB: {e}")

        # ── Instagram ──
        if ig_ready and filename not in ig_done:
            print("  📸 Uploading to Instagram...")
            try:
                ig_media_id = upload_to_instagram(
                    ig_user_id, ig_token, video_path, row)
                print(f"  ✅  Instagram — media ID: {ig_media_id}")
                if filename in rows_by_file:
                    rows_by_file[filename]["instagram"] = "✅"
                    save_csv()
            except Exception as e:
                print(f"  ❌  Instagram failed: {e}")
                errors.append(f"IG: {e}")

        # ── TikTok ──
        if tt_ready and filename not in tt_done:
            print("  🎵 Uploading to TikTok...")
            try:
                tt_publish_id = upload_to_tiktok(
                    tt_access_token, tt_open_id, video_path, row)
                print(f"  ✅  TikTok — publish ID: {tt_publish_id}")
                if filename in rows_by_file:
                    rows_by_file[filename]["tiktok"] = "✅"
                    save_csv()
                _log_tt_result(tt_results_file, filename, title, tt_publish_id)
            except Exception as e:
                print(f"  ❌  TikTok failed: {e}")
                errors.append(f"TT: {e}")

        print()
        any_success = bool(yt_video_id or fb_video_id or ig_media_id or tt_publish_id)
        status = "success" if not errors else ("partial" if any_success else "error")
        log_result(results_file, {
            "file": filename, "title": title,
            "fb_video_id": fb_video_id, "ig_media_id": ig_media_id,
            "status": status, "error": "; ".join(errors),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        })
        if errors and not any_success:
            fail += 1
        else:
            success += 1

    print("─" * 60)
    if dry_run:
        print(f"  DRY RUN complete — {len(to_upload)} video(s) validated.")
    else:
        print(f"  Done.  ✅ {success} uploaded   ❌ {fail} failed")
        if fail:
            print(f"  See {results_file} for details. Re-run to retry.")
    print()


def _log_tt_result(tt_results_file: str, filename: str, title: str, publish_id: str):
    """Append a success row to TikTok's results file."""
    path = Path(tt_results_file)
    fieldnames = ["file", "title", "tt_publish_id", "status", "uploaded_at"]
    existing = {}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[row.get("file", "")] = row
    existing[filename] = {
        "file":          filename,
        "title":         title,
        "tt_publish_id": publish_id,
        "status":        "success",
        "uploaded_at":   datetime.now(timezone.utc).isoformat(),
    }
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing.values())


def _log_yt_result(yt_results_file: str, filename: str, title: str, video_id: str):
    """Append a success row to YouTube's upload_results.csv."""
    path = Path(yt_results_file)
    fieldnames = ["file", "title", "video_id", "url", "status"]
    existing = {}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[row.get("file", "")] = row
    existing[filename] = {
        "file":     filename,
        "title":    title,
        "video_id": video_id,
        "url":      f"https://www.youtube.com/watch?v={video_id}",
        "status":   "success",
    }
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing.values())
