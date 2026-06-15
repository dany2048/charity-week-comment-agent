"""Fetch open DM conversations (Messenger + Instagram Direct) whose latest message
is from the user (i.e. awaiting our reply), tag each with a 24h-window flag, and
write state/dms_pending.json.

DMs are stateless: 'actionable' = the user sent the last message and we haven't
replied. Once we reply, the conversation drops out naturally — so unlike comments
this needs no seen-id tracking; the DMs tab is rebuilt fresh each run.
"""

import datetime
import json
import os
import sys
import meta_client

STATE = os.environ.get("CW_STATE_DIR", "state")
OUT = os.path.join(STATE, "dms_pending.json")
SEEN = os.path.join(STATE, "seen_dms.json")


def _key(r):
    return f"{r['comment_id']}|{r['published_at']}"  # recipient + message time


def main(n=15):
    msgr, mc = meta_client.fetch_messenger_dms(n)
    ig, ic = meta_client.fetch_ig_dms(n)
    all_rows = msgr + ig
    print(f"Messenger: {len(mc)} convos, {len(msgr)} awaiting reply  ·  IG DM: {len(ic)} convos, {len(ig)} awaiting reply")

    # seen-tracking so a still-unanswered DM isn't re-surfaced every run
    seen = set(json.load(open(SEEN))) if os.path.exists(SEEN) else set()
    rows = [r for r in all_rows if _key(r) not in seen]
    for r in all_rows:
        seen.add(_key(r))
    json.dump(sorted(seen), open(SEEN, "w"))

    now = datetime.datetime.now(datetime.timezone.utc)
    for r in rows:
        try:
            # Graph returns e.g. "2026-06-15T08:14:26+0000" (offset without colon)
            t = datetime.datetime.strptime(r["published_at"], "%Y-%m-%dT%H:%M:%S%z")
            r["within_24h"] = (now - t).total_seconds() < 24 * 3600
        except Exception:
            r["within_24h"] = None

    json.dump(rows, open(OUT, "w"), indent=2, ensure_ascii=False)
    print(f"{len(rows)} actionable DMs → {OUT}")
    for r in rows:
        w = "✓24h" if r["within_24h"] else ("stale>24h" if r["within_24h"] is False else "?")
        print(f"  [{r['platform']} {w}] {r['author']}: {r['comment_text'][:70]!r}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 15)
