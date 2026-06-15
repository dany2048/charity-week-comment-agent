"""Fetch unanswered top-level comments for ONLY the channel's most recent N videos
(default 6). Replaces the whole-channel sweep so we never necro-reply to decade-
old comments. Writes state/comments_pending.json with video titles attached.
"""

import json
import os
import sys
from youtube_client import get_service, CHANNEL_ID

STATE_DIR = os.environ.get("CW_STATE_DIR", "state")
PENDING_PATH = os.path.join(STATE_DIR, "comments_pending.json")
SEEN_PATH = os.path.join(STATE_DIR, "seen_ids.json")


def uploads_playlist_id(yt):
    resp = yt.channels().list(part="contentDetails", id=CHANNEL_ID).execute()
    return resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def recent_videos(yt, n):
    pl = uploads_playlist_id(yt)
    resp = yt.playlistItems().list(part="snippet,contentDetails", playlistId=pl, maxResults=n).execute()
    vids = []
    for it in resp.get("items", []):
        vids.append({
            "video_id": it["contentDetails"]["videoId"],
            "title": it["snippet"]["title"],
            "published_at": it["contentDetails"].get("videoPublishedAt", ""),
        })
    return vids


def comments_for_video(yt, video_id):
    out, page_token, pages = [], None, 0
    while pages < 10:
        try:
            resp = yt.commentThreads().list(
                part="snippet,replies", videoId=video_id, maxResults=100,
                order="time", textFormat="plainText", pageToken=page_token,
            ).execute()
        except Exception as e:  # comments disabled, etc.
            print(f"  ! {video_id}: {e}")
            break
        for item in resp.get("items", []):
            top = item["snippet"]["topLevelComment"]
            sn = top["snippet"]
            replied = any(
                r["snippet"].get("authorChannelId", {}).get("value") == CHANNEL_ID
                for r in item.get("replies", {}).get("comments", [])
            )
            out.append({
                "comment_id": top["id"],
                "video_id": video_id,
                "author": sn.get("authorDisplayName", ""),
                "comment_text": sn.get("textDisplay", ""),
                "published_at": sn.get("publishedAt", ""),
                "channel_already_replied": replied,
            })
        page_token = resp.get("nextPageToken")
        pages += 1
        if not page_token:
            break
    return out


def main(n=6):
    yt = get_service()
    vids = recent_videos(yt, n)
    title_by_id = {v["video_id"]: v["title"] for v in vids}
    print(f"Last {len(vids)} videos:")
    for v in vids:
        print(f"  - {v['video_id']}  {v['title'][:70]}")

    all_comments = []
    for v in vids:
        cs = comments_for_video(yt, v["video_id"])
        for c in cs:
            c["video_title"] = title_by_id.get(c["video_id"], "")
        all_comments.append((v, cs))

    actionable = [c for _, cs in all_comments for c in cs if not c["channel_already_replied"]]
    with open(PENDING_PATH, "w") as f:
        json.dump(actionable, f, indent=2, ensure_ascii=False)

    # mark everything seen
    seen = set()
    if os.path.exists(SEEN_PATH):
        seen = set(json.load(open(SEEN_PATH)))
    for _, cs in all_comments:
        for c in cs:
            seen.add(c["comment_id"])
    json.dump(sorted(seen), open(SEEN_PATH, "w"))

    print(f"\n{len(actionable)} unanswered comments across the last {len(vids)} videos → {PENDING_PATH}")
    per_vid = {}
    for c in actionable:
        per_vid[c["video_title"][:50]] = per_vid.get(c["video_title"][:50], 0) + 1
    for t, n_ in sorted(per_vid.items(), key=lambda x: -x[1]):
        print(f"   {n_:>3}  {t}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
