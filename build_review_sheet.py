"""Build the human-facing review sheet as TWO tabs on the same spreadsheet:
  - "YouTube"  — YouTube comments
  - "Meta"     — Facebook + Instagram comments

Each tab: a formatted instructions panel, then one row per pending comment
(full text), a Platform dropdown, a Suggested Reply, a Status dropdown
(Approved / Don't Answer / Needs Edit / Posted), and a 'Your comments' column.

Reads state/drafts.json + state/comments_pending.json. Rebuilds both tabs.
Run: python build_review_sheet.py
"""

import json
import os
from googleapiclient.discovery import build
from google_auth import get_credentials

SHEET_ID = os.environ["CW_APPROVAL_SHEET_ID"]
STATE = os.environ.get("CW_STATE_DIR", "state")

STATUS_OPTIONS = ["Approved", "Don't Answer", "Needs Edit", "Posted"]
# tab -> the Platform dropdown options valid on that tab
TABS = {"YouTube": ["YouTube"], "Meta": ["Facebook", "Instagram"],
        "DMs": ["Messenger", "Instagram DM"]}
PLATFORM_TO_TAB = {"YouTube": "YouTube", "Facebook": "Meta", "Instagram": "Meta",
                   "Messenger": "DMs", "Instagram DM": "DMs"}

PLATFORM_COL, STATUS_COL = 0, 5
HEADERS = ["Platform", "Source", "Author", "Comment", "Suggested Reply", "Status",
           "Your comments", "Why (our recommendation)", "comment_id"]
NCOLS = len(HEADERS)


def intro(tab):
    where = {"YouTube": "YouTube", "Meta": "Facebook / Instagram",
             "DMs": "Messenger / Instagram Direct"}[tab]
    kind = "DM" if tab == "DMs" else "COMMENT"
    surface = "sent privately" if tab == "DMs" else "posted publicly"
    rows = [
        [f"📋  CHARITY WEEK — {tab.upper()} {kind} REVIEW"],
        [f"Replies are {surface} AS Charity Week on {where}. Nothing sends until you approve it here."],
        [""],
        ["HOW TO USE  →  In the Status column choose:  ✅ Approved (we send the Suggested Reply as-is)  ·  🚫 Don't Answer (leave it, even if a reply was drafted)  ·  ✏️ Needs Edit (fix the reply text first, then set Approved). 'Posted' is set automatically after we send. Use 'Your comments' for notes."],
        ["VOICE  →  Warm, sincere, short. \"JazakAllahu kheyran\", \"Allah swt\", 🧡💙. Never a ruling/fatwa. Only verifiable facts — never a made-up hadith, ayah, name or number. Never promise donations/help. When in doubt: Don't Answer."],
    ]
    if tab == "DMs":
        rows.append(["⏰ 24-HOUR RULE  →  Meta only lets us auto-send a DM within 24h of the person's last message. The 'Why' column flags each as 'within 24h, sendable' or '>24h, reply manually in Meta inbox'. For stale ones, copy the Suggested Reply into the Meta inbox by hand."])
    rows.append(["PRE-FILLED  →  Scams / heavy / sectarian messages are pre-marked 'Don't Answer'. The sincere ones are left blank for you to approve. You have the final say on every row."])
    rows.append([""])
    return rows


def build_tab(svc, gid, tab, drafts, pending):
    INTRO = intro(tab)
    header_row = len(INTRO) + 1
    first_data = header_row + 1
    last_data = header_row + max(len(drafts), 1)

    rows = list(INTRO) + [HEADERS]
    for d in drafts:
        full = pending.get(d["comment_id"], {}).get("comment_text", d.get("comment_text", ""))
        source = d.get("source_title") or d.get("video_title") or d.get("source") or d.get("video_id", "")
        rows.append([
            d.get("platform", "YouTube"), source, d.get("author", ""), full,
            d.get("draft_reply", ""), d.get("status_default", ""), "",
            d.get("reason", ""), d["comment_id"],
        ])

    svc.values().clear(spreadsheetId=SHEET_ID, range=tab).execute()
    svc.values().update(spreadsheetId=SHEET_ID, range=f"{tab}!A1",
                        valueInputOption="USER_ENTERED", body={"values": rows}).execute()

    def grid(r0, r1, c0, c1):
        return {"sheetId": gid, "startRowIndex": r0, "endRowIndex": r1,
                "startColumnIndex": c0, "endColumnIndex": c1}

    reqs = [
        {"updateSheetProperties": {
            "properties": {"sheetId": gid, "gridProperties": {"frozenRowCount": header_row}},
            "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {"range": grid(0, 1, 0, NCOLS),
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 14,
                "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "backgroundColor": {"red": 0.12, "green": 0.16, "blue": 0.22}}},
            "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
        {"repeatCell": {"range": grid(1, len(INTRO), 0, NCOLS),
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "textFormat": {"fontSize": 10}}},
            "fields": "userEnteredFormat(wrapStrategy,textFormat)"}},
    ]
    for i in range(len(INTRO)):
        reqs.append({"mergeCells": {"range": grid(i, i + 1, 0, NCOLS), "mergeType": "MERGE_ALL"}})

    reqs += [
        {"repeatCell": {"range": grid(header_row - 1, header_row, 0, NCOLS),
            "cell": {"userEnteredFormat": {
                "backgroundColor": {"red": 0.18, "green": 0.45, "blue": 0.45},
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "wrapStrategy": "WRAP", "verticalAlignment": "MIDDLE"}},
            "fields": "userEnteredFormat(backgroundColor,textFormat,wrapStrategy,verticalAlignment)"}},
        {"repeatCell": {"range": grid(first_data - 1, last_data, 0, NCOLS),
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
            "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}},
        # Platform dropdown (col A)
        {"setDataValidation": {"range": grid(first_data - 1, last_data, PLATFORM_COL, PLATFORM_COL + 1),
            "rule": {"condition": {"type": "ONE_OF_LIST",
                "values": [{"userEnteredValue": o} for o in TABS[tab]]},
                "showCustomUi": True, "strict": False}}},
        # Status dropdown (col F)
        {"setDataValidation": {"range": grid(first_data - 1, last_data, STATUS_COL, STATUS_COL + 1),
            "rule": {"condition": {"type": "ONE_OF_LIST",
                "values": [{"userEnteredValue": o} for o in STATUS_OPTIONS]},
                "showCustomUi": True, "strict": False}}},
        {"addConditionalFormatRule": {"rule": {
            "ranges": [grid(first_data - 1, last_data, STATUS_COL, STATUS_COL + 1)],
            "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Approved"}]},
                "format": {"backgroundColor": {"red": 0.80, "green": 0.94, "blue": 0.80}}}}, "index": 0}},
        {"addConditionalFormatRule": {"rule": {
            "ranges": [grid(first_data - 1, last_data, STATUS_COL, STATUS_COL + 1)],
            "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Don't Answer"}]},
                "format": {"backgroundColor": {"red": 0.90, "green": 0.90, "blue": 0.90}}}}, "index": 0}},
        {"addConditionalFormatRule": {"rule": {
            "ranges": [grid(first_data - 1, last_data, STATUS_COL, STATUS_COL + 1)],
            "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Needs Edit"}]},
                "format": {"backgroundColor": {"red": 0.99, "green": 0.91, "blue": 0.72}}}}, "index": 0}},
        {"addConditionalFormatRule": {"rule": {
            "ranges": [grid(first_data - 1, last_data, STATUS_COL, STATUS_COL + 1)],
            "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Posted"}]},
                "format": {"backgroundColor": {"red": 0.78, "green": 0.85, "blue": 0.97}}}}, "index": 0}},
    ]

    widths = [100, 200, 130, 330, 300, 110, 190, 220, 170]
    for i, w in enumerate(widths):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"}})

    svc.batchUpdate(spreadsheetId=SHEET_ID, body={"requests": reqs}).execute()
    return len(drafts)


def main():
    svc = build("sheets", "v4", credentials=get_credentials(), cache_discovery=False).spreadsheets()
    drafts = json.load(open(os.path.join(STATE, "drafts.json")))
    pending = {c["comment_id"]: c for c in json.load(open(os.path.join(STATE, "comments_pending.json")))}

    by_tab = {t: [] for t in TABS}
    for d in drafts:
        by_tab[PLATFORM_TO_TAB.get(d.get("platform", "YouTube"), "YouTube")].append(d)

    meta = svc.get(spreadsheetId=SHEET_ID).execute()
    ids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    add = [{"addSheet": {"properties": {"title": t}}} for t in TABS if t not in ids]
    if add:
        svc.batchUpdate(spreadsheetId=SHEET_ID, body={"requests": add}).execute()
        meta = svc.get(spreadsheetId=SHEET_ID).execute()
        ids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}

    for tab in TABS:
        n = build_tab(svc, ids[tab], tab, by_tab[tab], pending)
        print(f"  {tab}: {n} comments")

    # remove any leftover tabs (old single 'Replies', default 'Sheet1')
    drop = [{"deleteSheet": {"sheetId": ids[t]}} for t in ids if t not in TABS]
    if drop:
        svc.batchUpdate(spreadsheetId=SHEET_ID, body={"requests": drop}).execute()

    print(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")


if __name__ == "__main__":
    main()
