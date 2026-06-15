"""The 'Needs Edit' feedback loop.

When a reviewer sets Status = "Needs Edit" and writes an instruction in the
"Your comments" column, the daily run revises that row's Suggested Reply to match
— the rewrite itself is done by Claude (subscription), this script is just I/O:

  export : pull all 'Needs Edit' rows that have a reviewer instruction
           → state/edits_pending.json   (Claude then writes state/edits_revised.json)
  apply  : write the revised replies back into the Suggested Reply cells, clear the
           reviewer's instruction (consumed), and reset Status to blank for re-approval.

Usage: python revise_edits.py export   |   python revise_edits.py apply
"""

import json
import os
import sys
from sheets_client import (_svc, _values, _header_row, SHEET_ID, TABS, NCOLS,
                           PLATFORM_COL, REPLY_COL, STATUS_COL, CID_COL)

SOURCE_COL, COMMENT_COL, YOURCOMMENTS_COL = 1, 3, 6
STATE = os.environ.get("CW_STATE_DIR", "state")
PENDING = os.path.join(STATE, "edits_pending.json")
REVISED = os.path.join(STATE, "edits_revised.json")


def _col(c):
    return chr(ord("A") + c)


def export_edits():
    out = []
    for tab in TABS:
        vals = _values(tab)
        h = _header_row(vals)
        if h is None:
            continue
        for i in range(h + 1, len(vals)):
            row = list(vals[i]) + [""] * (NCOLS - len(vals[i]))
            if row[STATUS_COL].strip().lower() == "needs edit" and row[YOURCOMMENTS_COL].strip():
                out.append({
                    "tab": tab, "row_index": i + 1, "platform": row[PLATFORM_COL],
                    "source": row[SOURCE_COL], "comment": row[COMMENT_COL],
                    "current_reply": row[REPLY_COL], "instruction": row[YOURCOMMENTS_COL],
                    "comment_id": row[CID_COL],
                })
    json.dump(out, open(PENDING, "w"), indent=2, ensure_ascii=False)
    print(f"{len(out)} 'Needs Edit' rows with instructions → {PENDING}")
    print("Next: Claude rewrites each Suggested Reply per cw_voice.md + the reviewer's "
          "instruction → write state/edits_revised.json as [{tab,row_index,new_reply}], then `apply`.")


def apply_edits():
    revised = json.load(open(REVISED))
    data = []
    for r in revised:
        ri = r["row_index"]; tab = r["tab"]
        data.append({"range": f"{tab}!{_col(REPLY_COL)}{ri}", "values": [[r["new_reply"]]]})
        data.append({"range": f"{tab}!{_col(STATUS_COL)}{ri}", "values": [[""]]})        # back to pending
        data.append({"range": f"{tab}!{_col(YOURCOMMENTS_COL)}{ri}", "values": [[""]]})  # instruction consumed
    if data:
        _svc().values().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"valueInputOption": "USER_ENTERED", "data": data}).execute()
    print(f"Applied {len(revised)} revised replies; Status reset to blank for re-approval.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "export"
    (export_edits if mode == "export" else apply_edits)()
