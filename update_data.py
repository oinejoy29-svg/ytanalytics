import json
import os
import requests
from datetime import datetime, timezone

API_KEY = os.environ["YOUTUBE_API_KEY"]
CHANNEL_ID = "UCiLmCoftZHWXSFuQlnEJSsQ"

DATA_FILE = "data.json"


def youtube_api(endpoint, params):
    params["key"] = API_KEY

    response = requests.get(
        f"https://www.googleapis.com/youtube/v3/{endpoint}",
        params=params,
        timeout=30
    )

    response.raise_for_status()
    return response.json()


def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "subscribers": [],
            "videos": []
        }

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def get_channel():
    data = youtube_api(
        "channels",
        {
            "part": "snippet,statistics",
            "id": CHANNEL_ID
        }
    )

    if not data.get("items"):
        raise Exception("チャンネルが見つかりません")

    return data["items"][0]





def get_video_ids(channel):
    uploads_playlist = channel["contentDetails"]["relatedPlaylists"]["uploads"]

    videos = []
    page_token = None

    while True:
        params = {
            "part": "snippet",
            "playlistId": uploads_playlist,
            "maxResults": 50
        }

        if page_token:
            params["pageToken"] = page_token

        result = youtube_api(
            "playlistItems",
            params
        )

        for item in result.get("items", []):
            videos.append(
                {
                    "id": item["snippet"]["resourceId"]["videoId"],
                    "date": item["snippet"]["publishedAt"][:10]
                }
            )

        page_token = result.get("nextPageToken")

        if not page_token:
            break

    return videos


def get_video_details(video_ids):
    videos = []

    for start in range(0, len(video_ids), 50):
        batch = video_ids[start:start + 50]

        result = youtube_api(
            "videos",
            {
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(
                    video["id"]
                    for video in batch
                )
            }
        )

        for item in result.get("items", []):
            duration = item["contentDetails"]["duration"]

            videos.append(
                {
                    "id": item["id"],
                    "title": item["snippet"]["title"],
                    "date": item["snippet"]["publishedAt"][:10],
                    "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                    "duration": iso_duration_to_hms(duration),
                    "durationSeconds": iso_duration_to_seconds(duration),
                    "viewCount": int(
                        item["statistics"].get("viewCount", 0)
                    ),
                    "tags": []
                }
            )

    return videos


def iso_duration_to_seconds(value):
    import re

    match = re.match(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        value
    )

    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return (
        hours * 3600
        + minutes * 60
        + seconds
    )


def iso_duration_to_hms(value):
    return format_duration(
        iso_duration_to_seconds(value)
    )


def format_duration(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"

    return f"{minutes}:{seconds:02d}"


def main():
    data = load_data()

    channel = get_channel()

    # 登録者数
    subscribers = int(
        channel["statistics"].get(
            "subscriberCount",
            0
        )
    )

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    existing = next(
        (
            item
            for item in data["subscribers"]
            if item["date"] == today
        ),
        None
    )

    if existing:
        existing["count"] = subscribers
    else:
        data["subscribers"].append(
            {
                "date": today,
                "count": subscribers
            }
        )

    # 動画
    video_ids = get_video_ids(channel)
    video_details = get_video_details(video_ids)

    # 既存データを維持しながら更新
    existing_videos = {
        video["id"]: video
        for video in data.get("videos", [])
        if video.get("id")
    }

    for video in video_details:
        old = existing_videos.get(video["id"])

        if old:
            # 手動タグなどは維持
            if old.get("tags"):
                video["tags"] = old["tags"]

        existing_videos[video["id"]] = video

    data["videos"] = list(
        existing_videos.values()
    )

    data["subscribers"].sort(
        key=lambda x: x["date"]
    )

    data["videos"].sort(
        key=lambda x: x["date"],
        reverse=True
    )

    save_data(data)

    print(
        f"登録者数: {subscribers}"
    )

    print(
        f"動画数: {len(data['videos'])}"
    )


if __name__ == "__main__":
    main()
