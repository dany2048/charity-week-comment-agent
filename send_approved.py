"""Step 5 (I/O): post the replies the CW volunteers approved in the Google Sheet.

Reads Approve?=Yes rows, posts each via the YouTube API (using the possibly
edited text in the sheet), marks the row 'Posted'. Run this on a later schedule
(e.g. a few hours after the digest, and/or the next morning) so volunteers have
time to review. Safe to run repeatedly — Posted rows are skipped.
"""

import json
import os
import sys
from sheets_client import read_approved, mark_status

STATE_DIR = os.environ.get("CW_STATE_DIR", "state")
LOG_PATH = os.path.join(STATE_DIR, "sent_log.jsonl")


def post_reply(platform, target_id, text):
    """Route an approved reply to the right API (imported lazily so a missing
    Meta token never blocks a YouTube-only run, and vice versa).
      Facebook/Instagram → comment reply ; Messenger/Instagram DM → send a DM."""
    if platform in ("Messenger", "Instagram DM"):
        import meta_client
        return meta_client.send_dm(platform, target_id, text)  # target_id = recipient id
    if platform in ("Facebook", "Instagram"):
        import meta_client
        return meta_client.reply(platform, target_id, text)
    import youtube_client
    return youtube_client.post_reply(target_id, text)


def log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main(date_str):
    approved = read_approved()
    sent = 0
    for row in approved:
        if not row["reply"].strip() or not row["comment_id"].strip():
            mark_status(row["tab"], row["row_index"], "Skipped (empty)")
            continue
        try:
            rid = post_reply(row["platform"], row["comment_id"], row["reply"])
            mark_status(row["tab"], row["row_index"], "Posted")
            log({"date": date_str, "platform": row["platform"], "comment_id": row["comment_id"],
                 "reply": row["reply"], "bucket": "APPROVED", "result": "sent", "reply_id": rid})
            sent += 1
        except Exception as e:  # noqa: BLE001
            mark_status(row["tab"], row["row_index"], "Failed")
            log({"date": date_str, "comment_id": row["comment_id"], "result": "error", "error": str(e)})
    print(f"Posted {sent} approved replies ({len(approved)} were marked Approved)")
    return sent


if __name__ == "__main__":
    date_str = sys.argv[1] if len(sys.argv) > 1 else "unknown-date"
    main(date_str)
