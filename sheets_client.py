"""Google Sheet = the approval surface the CW volunteers use. TWO tabs:
  "YouTube" and "Meta" (Facebook + Instagram). Each tab is built by
  build_review_sheet.py: an instructions panel, a header row, then one row per
  comment. Columns:
    A Platform | B Source | C Author | D Comment | E Suggested Reply | F Status | G Your comments | H Why | I comment_id

Reviewers set column F (Status): Approved / Don't Answer / Needs Edit / Posted.
The send step posts the Approved rows (column E text) and stamps them Posted,
routing by Platform. Auth: the shared contentbase1 OAuth token (Sheets scope).
"""

import os
from googleapiclient.discovery import build
from google_auth import get_credentials

SHEET_ID = os.environ.get("CW_APPROVAL_SHEET_ID", "")
TABS = ["YouTube", "Meta", "DMs"]
PLATFORM_TO_TAB = {"YouTube": "YouTube", "Facebook": "Meta", "Instagram": "Meta",
                   "Messenger": "DMs", "Instagram DM": "DMs"}

# table layout (0-based column indices)
PLATFORM_COL, REPLY_COL, STATUS_COL, CID_COL, NCOLS = 0, 4, 5, 8, 9
HEADER_KEY = "comment_id"

# kept for create_sheet.py compatibility
HEADER = ["Platform", "Source", "Author", "Comment", "Suggested Reply", "Status",
          "Your comments", "Why (our recommendation)", "comment_id"]
WORKSHEET = "YouTube"


def _svc():
    return build("sheets", "v4", credentials=get_credentials(), cache_discovery=False).spreadsheets()


def _values(tab):
    return _svc().values().get(spreadsheetId=SHEET_ID, range=tab).execute().get("values", [])


def _header_row(values):
    for i, row in enumerate(values):
        if any(str(c).strip() == HEADER_KEY for c in row):
            return i
    return None


def existing_comment_ids():
    """Every comment_id already present across all tabs — the sheet is the state,
    so this is what makes the daily run idempotent without seen-id files."""
    ids = set()
    for tab in TABS:
        values = _values(tab)
        h = _header_row(values)
        if h is None:
            continue
        for i in range(h + 1, len(values)):
            row = list(values[i]) + [""] * (NCOLS - len(values[i]))
            if row[CID_COL].strip():
                ids.add(row[CID_COL].strip())
    return ids


def append_drafts(drafts, date_str):
    """Append new pending comments below each tab's table (daily incremental).

    Dedupes against the sheet: any comment_id already on a tab is skipped, so a
    re-fetched but still-awaiting-review comment is never duplicated.

    Writes at an EXPLICIT end-of-sheet row via values.update (NOT values.append —
    the merged-cell instruction panel breaks Google's table auto-detection and
    drops rows into the middle of the panel). Uses RAW so long numeric comment_ids
    stay exact text instead of being mangled into scientific notation.
    """
    svc = _svc()
    have = existing_comment_ids()
    total = 0
    for tab in TABS:
        rows = []
        for d in drafts:
            if d["comment_id"] in have:
                continue  # already on the sheet — the sheet is the source of truth
            if PLATFORM_TO_TAB.get(d.get("platform", "YouTube"), "YouTube") != tab:
                continue
            source = d.get("source_title") or d.get("video_title") or d.get("source") or d.get("video_id", "")
            rows.append([
                d.get("platform", "YouTube"), source, d.get("author", ""),
                d.get("comment_text", ""), d.get("draft_reply", ""),
                d.get("status_default", ""), "", d.get("reason", ""), str(d["comment_id"]),
            ])
        if rows:
            start = len(_values(tab)) + 1          # 1-based row after the last non-empty row
            end = start + len(rows) - 1
            last_col = chr(ord("A") + NCOLS - 1)    # 'I'
            svc.values().update(
                spreadsheetId=SHEET_ID, range=f"{tab}!A{start}:{last_col}{end}",
                valueInputOption="RAW", body={"values": rows},
            ).execute()
            total += len(rows)
    return total


def read_approved():
    """Rows across both tabs marked Status=Approved (not yet Posted).

    Each item: {tab, row_index (1-based), platform, comment_id, reply}.
    """
    out = []
    for tab in TABS:
        values = _values(tab)
        h = _header_row(values)
        if h is None:
            continue
        for i in range(h + 1, len(values)):
            row = list(values[i]) + [""] * (NCOLS - len(values[i]))
            if row[STATUS_COL].strip().lower() == "approved" and row[CID_COL].strip():
                out.append({"tab": tab, "row_index": i + 1,
                            "platform": row[PLATFORM_COL].strip() or "YouTube",
                            "comment_id": row[CID_COL], "reply": row[REPLY_COL]})
    return out


def mark_status(tab, row_index, status):
    """Write the Status cell (column F) for a 1-based row on `tab`."""
    col = chr(ord("A") + STATUS_COL)  # 'F'
    _svc().values().update(
        spreadsheetId=SHEET_ID, range=f"{tab}!{col}{row_index}",
        valueInputOption="USER_ENTERED", body={"values": [[status]]},
    ).execute()


if __name__ == "__main__":
    print(f"Sheet {SHEET_ID} — {len(read_approved())} rows marked Approved pending send")
