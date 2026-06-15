"""Step 1 of the daily run (I/O): pull NEW YouTube comments → comments_pending.json.

Tracks already-seen comment ids in state/seen_ids.json so each run only handles
new comments. The drafting/triage happens AFTER this, done by the Claude run
itself reading comments_pending.json + cw_voice.md (no LLM API key here).
"""

import json
import os
from youtube_client import fetch_new_comments

STATE_DIR = os.environ.get("CW_STATE_DIR", "state")
SEEN_PATH = os.path.join(STATE_DIR, "seen_ids.json")
PENDING_PATH = os.path.join(STATE_DIR, "comments_pending.json")


def load_seen():
    if os.path.exists(SEEN_PATH):
        with open(SEEN_PATH) as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(SEEN_PATH, "w") as f:
        json.dump(sorted(seen), f)


def main():
    seen = load_seen()
    new = fetch_new_comments(seen_ids=seen)
    # only surface comments the channel hasn't already replied to
    actionable = [c for c in new if not c["channel_already_replied"]]
    with open(PENDING_PATH, "w") as f:
        json.dump(actionable, f, indent=2, ensure_ascii=False)
    # mark everything we saw as seen so we never reprocess it
    for c in new:
        seen.add(c["comment_id"])
    save_seen(seen)
    print(f"{len(actionable)} new actionable comments → {PENDING_PATH}")
    print("Next: Claude drafts/triages per cw_voice.md → write drafts.json")


if __name__ == "__main__":
    main()
