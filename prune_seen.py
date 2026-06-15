"""Drop pending items whose comment_id is already on the review sheet — the sheet
is the source of truth, so this keeps the daily triage from re-thinking comments
that are already handled (or awaiting review). Run after the fetch_* scripts and
before triage. Correctness is also guaranteed at append time; this just saves the
wasted re-triage on a stateless cloud run.
"""

import json
import os
from sheets_client import existing_comment_ids

STATE = os.environ.get("CW_STATE_DIR", "state")


def main():
    have = existing_comment_ids()
    for fn in ("comments_pending.json", "dms_pending.json"):
        p = os.path.join(STATE, fn)
        if not os.path.exists(p):
            continue
        items = json.load(open(p))
        new = [c for c in items if c.get("comment_id") not in have]
        json.dump(new, open(p, "w"), indent=2, ensure_ascii=False)
        print(f"{fn}: {len(new)} new (dropped {len(items) - len(new)} already on the sheet)")


if __name__ == "__main__":
    main()
