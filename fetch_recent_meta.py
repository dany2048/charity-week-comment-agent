"""Fetch unanswered comments on the last N FB posts + N IG media, and MERGE them
into state/comments_pending.json (alongside any YouTube comments already there).

Run AFTER fetch_recent.py in a daily run (fetch_recent.py overwrites the file;
this one appends). Dedupes by comment_id and marks everything seen.
"""

import json
import os
import sys
import meta_client

STATE = os.environ.get("CW_STATE_DIR", "state")
PENDING = os.path.join(STATE, "comments_pending.json")
SEEN = os.path.join(STATE, "seen_ids.json")


def main(n=6):
    fb, posts = meta_client.fetch_fb_comments(n)
    ig, media = meta_client.fetch_ig_comments(n)
    print(f"FB: {len(posts)} posts, {len(fb)} comments  ·  IG: {len(media)} media, {len(ig)} comments")

    fresh = [c for c in fb + ig if not c["channel_already_replied"]]

    existing = json.load(open(PENDING)) if os.path.exists(PENDING) else []
    have = {c["comment_id"] for c in existing}
    merged = existing + [c for c in fresh if c["comment_id"] not in have]
    json.dump(merged, open(PENDING, "w"), indent=2, ensure_ascii=False)

    seen = set(json.load(open(SEEN))) if os.path.exists(SEEN) else set()
    for c in fb + ig:
        seen.add(c["comment_id"])
    json.dump(sorted(seen), open(SEEN, "w"))

    added = len([c for c in fresh if c["comment_id"] not in have])
    print(f"+{added} Meta comments merged → {PENDING} (total pending: {len(merged)})")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
