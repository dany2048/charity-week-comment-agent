"""Step 3 of the daily run (I/O): take drafts.json (written by Claude) and:
  - AUTO-SEND the AUTO_SAFE replies immediately (no human needed)
  - push REVIEW / GENERIC_ONLY drafts to the approval Google Sheet (Pending)
  - SKIP items are ignored (logged only)

Usage: python push_drafts.py 2026-06-08
(the date is passed by the daily run so scripts don't read the clock directly)
"""

import json
import os
import sys
from sheets_client import append_drafts


def post_reply(platform, target_id, text):
    """Route to the right platform API (lazy import)."""
    if platform in ("Messenger", "Instagram DM"):
        import meta_client
        return meta_client.send_dm(platform, target_id, text)
    if platform in ("Facebook", "Instagram"):
        import meta_client
        return meta_client.reply(platform, target_id, text)
    import youtube_client
    return youtube_client.post_reply(target_id, text)

STATE_DIR = os.environ.get("CW_STATE_DIR", "state")
DRAFTS_PATH = os.path.join(STATE_DIR, "drafts.json")
LOG_PATH = os.path.join(STATE_DIR, "sent_log.jsonl")
NUDGE_PATH = os.path.join(STATE_DIR, "nudge.txt")
SHEET_URL = os.environ.get("CW_APPROVAL_SHEET_URL", "[approval sheet link]")


def write_nudge(queued):
    """Write the ready-to-paste WhatsApp line for Marya to drop in the CW group."""
    if queued <= 0:
        msg = ""  # nothing to review today; no nudge needed
    else:
        msg = (
            f"Salam everyone \U0001F90D {queued} drafted comment "
            f"{'reply is' if queued == 1 else 'replies are'} ready for a quick review:\n"
            f"{SHEET_URL}\n"
            f"Set Approve? = Yes on the ones you're happy with (edit the text if you like), "
            f"leave the rest. JazakAllah khayran \U0001F932"
        )
    with open(NUDGE_PATH, "w") as f:
        f.write(msg)
    return msg


def log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# HOLD_FOR_REVIEW (default ON): nothing auto-posts; every draft (incl. AUTO_SAFE)
# is appended to the review sheet for the volunteers. Set CW_HOLD_FOR_REVIEW=0 to
# re-enable AUTO_SAFE auto-send once the volunteers trust the agent.
HOLD = os.environ.get("CW_HOLD_FOR_REVIEW", "1") != "0"


def main(date_str):
    with open(DRAFTS_PATH) as f:
        drafts = json.load(f)

    sent = 0
    if not HOLD:
        auto = [d for d in drafts if d["bucket"] == "AUTO_SAFE" and d.get("draft_reply")]
        for d in auto:
            try:
                rid = post_reply(d.get("platform", "YouTube"), d["comment_id"], d["draft_reply"])
                log({"date": date_str, "platform": d.get("platform", "YouTube"),
                     "comment_id": d["comment_id"], "reply": d["draft_reply"],
                     "bucket": "AUTO_SAFE", "result": "sent", "reply_id": rid})
                sent += 1
            except Exception as e:  # noqa: BLE001 - log and continue, never crash the batch
                log({"date": date_str, "comment_id": d["comment_id"], "bucket": "AUTO_SAFE",
                     "result": "error", "error": str(e)})

    # in HOLD mode append everything; otherwise AUTO_SAFE was just sent, queue the rest
    to_queue = drafts if HOLD else [d for d in drafts if d["bucket"] != "AUTO_SAFE"]
    queued = append_drafts(to_queue, date_str)
    skipped = sum(1 for d in drafts if d["bucket"] == "SKIP")

    write_nudge(queued)
    print(f"AUTO_SAFE auto-sent: {sent}")
    print(f"Queued for CW volunteer approval (sheet): {queued}")
    print(f"Skipped (left unanswered): {skipped}")
    if queued > 0:
        print(f"Nudge for Marya to paste in the CW WhatsApp group → {NUDGE_PATH}")
    return sent, queued, skipped


if __name__ == "__main__":
    date_str = sys.argv[1] if len(sys.argv) > 1 else "unknown-date"
    main(date_str)
