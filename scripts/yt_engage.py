"""yt_engage.py - post the channel's CTA comment on new uploads and optionally pin
a hit clip to the channel page (featured video) via the official YouTube Data API.

Limits (verified 2026-11): the API has NO endpoint to pin comments
(commentThreads: list/insert/update only, no "pinned" field). Pinning a comment
must be done manually in YouTube Studio. This script instead:
  1. posts the channel comment right after upload (first-comment position),
  2. optionally sets the channel featured video (brandingSettings.featuredVideoUrl).

Quota cost per daily round: ~450-500 units of the 10,000/day default.
"""

import os
import random
from datetime import datetime, timedelta, timezone

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"

CLIENT_ID = os.environ["YT_CLIENT_ID"]
CLIENT_SECRET = os.environ["YT_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["YT_REFRESH_TOKEN"]
CHANNEL_ID = os.environ.get("YT_CHANNEL_ID", "").strip()
TARGET_VIDEO_ID = os.environ.get("TARGET_VIDEO_ID", "").strip()
FEATURED_ENABLED = os.environ.get("FEATURED_ENABLED", "false").lower() == "true"

MAX_AGE_HOURS = 26

# Pool of CTA comments (Isan/Thai). Kept varied on purpose: identical text on
# every video looks templated and can be auto-flagged as spam. Edit freely.
COMMENTS = [
    "ยายบอกเด้อ กดติดตามไว้ก่อน เดี๋ยวตอนหน้ายายไปเจอบักลิงที่ไหนต่อ",
    "บักลิงตัวนี้มันหนีไม่พ้นหรอก กดติดตามรอดูว่ายายจะเอาผิดยังไง",
    "ใครเคยโดนคนในบ้านพังของแบบนี้ยกมือขึ้นหน่อย กดติดตามไว้เด้อ มีตอนต่อทุกวัน",
    "ยายมาให้พรคนที่กดติดตามวันนี้ ขอให้ของในบ้านแข็งแรงอยู่เน้อ",
    "ตอนต่อไปยายเตรียมของใหญ่กว่าเดิมรออยู่ กดติดตามห้ามพลาด",
    "บักลิงมันบอกว่ามิงกดติดตามป่ะล่ะ ยายเฝ้ามองอยู่นะ",
    "คนชุดหมามันกัดของจนหมดตู้แล้ว รอตอนหน้ายายจัดการเด้อ",
    "ใครชอบเห็นยายด่ารัว ๆ กดติดตามให้ยายมีกำลังใจเด้อ",
]


def get_access_token() -> str:
    r = requests.post(
        TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def api_get(url: str, token: str, params: dict):
    r = requests.get(url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    return r.json()


def api_post(url: str, token: str, body: dict, params: dict):
    r = requests.post(
        url, params=params, json=body, headers={"Authorization": f"Bearer {token}"}, timeout=30
    )
    r.raise_for_status()
    return r.json()


def uploads_playlist_id(token: str, channel_id: str) -> str:
    data = api_get(f"{API}/channels", token, {
        "part": "contentDetails",
        "id": channel_id,
    })
    items = data.get("items", [])
    if not items:
        raise SystemExit(f"channel {channel_id} not found")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def recent_video_ids(token: str, playlist_id: str, cutoff: datetime):
    vids = []
    page = None
    while True:
        params = {"part": "snippet", "playlistId": playlist_id, "maxResults": 50}
        if page:
            params["pageToken"] = page
        data = api_get(f"{API}/playlistItems", token, params)
        for it in data.get("items", []):
            sn = it["snippet"]
            if sn.get("channelId") != CHANNEL_ID:
                continue
            published = datetime.fromisoformat(
                sn["contentDetails"]["videoPublishedAt"].replace("Z", "+00:00")
            )
            if published >= cutoff:
                vids.append(sn["resourceId"]["videoId"])
        page = data.get("nextPageToken")
        if not page:
            break
    return vids


def channel_already_commented(token: str, video_id: str) -> bool:
    data = api_get(f"{API}/commentThreads", token, {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": 100,
        "order": "time",
    })
    for it in data.get("items", []):
        author = it["snippet"]["topLevelComment"]["snippet"].get("authorChannelId", {})
        if author.get("value") == CHANNEL_ID:
            return True
    return False


def post_comment(token: str, video_id: str, text: str):
    api_post(
        f"{API}/commentThreads", token,
        {
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {"snippet": {"videoId": video_id, "textOriginal": text}},
            }
        },
        {"part": "snippet"},
    )


def set_featured_video(token: str, video_id: str):
    ch = api_get(f"{API}/channels", token, {
        "part": "brandingSettings",
        "id": CHANNEL_ID,
    })
    branding = ch["items"][0]["brandingSettings"]
    branding.setdefault("channel", {})["featuredVideoUrl"] = (
        f"https://www.youtube.com/watch?v={video_id}"
    )
    api_post(f"{API}/channels", token, {"brandingSettings": branding}, {"part": "brandingSettings"})


def main():
    if not CHANNEL_ID:
        raise SystemExit("YT_CHANNEL_ID (repo variable) is required")
    token = get_access_token()

    rng = random.Random(datetime.now(timezone.utc).strftime("%Y%m%d"))
    pool = COMMENTS[:]
    rng.shuffle(pool)

    if TARGET_VIDEO_ID:
        targets = [TARGET_VIDEO_ID]
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
        pl = uploads_playlist_id(token, CHANNEL_ID)
        targets = recent_video_ids(token, pl, cutoff)

    posted, skipped = 0, 0
    for i, vid in enumerate(targets):
        if not TARGET_VIDEO_ID and channel_already_commented(token, vid):
            skipped += 1
            continue
        post_comment(token, vid, pool[i % len(pool)])
        print(f"comment posted on {vid}")
        posted += 1

    if FEATURED_ENABLED and targets:
        set_featured_video(token, targets[0])
        print(f"featured video set to {targets[0]}")

    note = ("NOTE: comment pinning is not available via the official YouTube API - "
            "pin manually in Studio if wanted. Featured-video pin IS API-supported.")
    print(f"done: posted={posted} skipped={skipped}")
    print(note)


if __name__ == "__main__":
    main()
