"""One-off: harvest the channel's OWN past replies (+ the comment they answered)
so we can model the existing CW reply voice instead of inventing one.

Scans comment threads across the channel, keeps every reply whose author is the
CW channel itself, pairs it with the parent comment text. Writes
state/past_replies.json and prints a sample.
"""

import json
import os
from youtube_client import get_service, CHANNEL_ID

OUT = os.path.join(os.environ.get("CW_STATE_DIR", "state"), "past_replies.json")


def main():
    if not CHANNEL_ID:
        raise SystemExit("Set CW_YT_CHANNEL_ID")
    yt = get_service()
    pairs, page_token, pages = [], None, 0
    while pages < 30:
        resp = yt.commentThreads().list(
            part="snippet,replies",
            allThreadsRelatedToChannelId=CHANNEL_ID,
            maxResults=100,
            order="time",
            textFormat="plainText",
            pageToken=page_token,
        ).execute()
        for item in resp.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            parent_text = top.get("textDisplay", "")
            for r in item.get("replies", {}).get("comments", []):
                rs = r["snippet"]
                if rs.get("authorChannelId", {}).get("value") == CHANNEL_ID:
                    pairs.append({
                        "parent": parent_text,
                        "reply": rs.get("textDisplay", ""),
                        "video_id": top.get("videoId", ""),
                    })
        page_token = resp.get("nextPageToken")
        pages += 1
        if not page_token:
            break
    with open(OUT, "w") as f:
        json.dump(pairs, f, indent=2, ensure_ascii=False)
    print(f"{len(pairs)} past channel replies → {OUT}\n")
    for p in pairs[:25]:
        print(f"  COMMENT: {p['parent'][:80]}")
        print(f"  REPLY  : {p['reply'][:120]}\n")


if __name__ == "__main__":
    main()
