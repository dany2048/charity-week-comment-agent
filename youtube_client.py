"""YouTube Data API v3 client for the Charity Week comment agent.

Two jobs only (I/O layer — no LLM here):
  - fetch new top-level comments across the CW channel's videos
  - post a reply to a given comment, AS the channel

Auth: OAuth installed-app flow. The authorizing Google account must have
manager/owner access to the CW YouTube channel. Scope youtube.force-ssl is
required to insert comments. Token (with refresh token) is cached to TOKEN_PATH.
"""

import os
from googleapiclient.discovery import build
from google_auth import get_credentials

CHANNEL_ID = os.environ.get("CW_YT_CHANNEL_ID", "")  # the CW channel id (UC...)


def get_service():
    """Return an authorized YouTube Data API service (shared contentbase1 OAuth token)."""
    return build("youtube", "v3", credentials=get_credentials(), cache_discovery=False)


def fetch_new_comments(seen_ids, max_pages=10):
    """Fetch top-level comments across all CW videos, skipping ids in `seen_ids`.

    Returns a list of dicts: {comment_id, video_id, author, comment_text,
    published_at, channel_already_replied}. Only NEW, not-yet-seen comments.
    """
    if not CHANNEL_ID:
        raise SystemExit("Set CW_YT_CHANNEL_ID to the CW channel id (UC...).")
    yt = get_service()
    out, page_token, pages = [], None, 0
    while pages < max_pages:
        resp = yt.commentThreads().list(
            part="snippet,replies",
            allThreadsRelatedToChannelId=CHANNEL_ID,
            maxResults=100,
            order="time",
            textFormat="plainText",
            pageToken=page_token,
        ).execute()
        for item in resp.get("items", []):
            top = item["snippet"]["topLevelComment"]
            cid = top["id"]
            if cid in seen_ids:
                # ordered by time desc; once we hit seen comments we can stop early
                return out
            sn = top["snippet"]
            # did the channel already reply in this thread?
            replied = False
            for r in item.get("replies", {}).get("comments", []):
                if r["snippet"].get("authorChannelId", {}).get("value") == CHANNEL_ID:
                    replied = True
                    break
            out.append({
                "comment_id": cid,
                "video_id": sn.get("videoId", ""),
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


def post_reply(parent_comment_id, text):
    """Post a reply to a top-level comment. Returns the new comment id."""
    yt = get_service()
    resp = yt.comments().insert(
        part="snippet",
        body={"snippet": {"parentId": parent_comment_id, "textOriginal": text}},
    ).execute()
    return resp["id"]


if __name__ == "__main__":
    # smoke test: print how many new comments are visible
    new = fetch_new_comments(seen_ids=set())
    print(f"{len(new)} comments visible across the channel")
    for c in new[:5]:
        flag = " (already replied)" if c["channel_already_replied"] else ""
        print(f"- [{c['video_id']}] {c['author']}: {c['comment_text'][:80]}{flag}")
