"""One-time: create the approval Google Sheet on contentbase1 and print its id/url.

Run AFTER the OAuth login (token.json exists). Creates a spreadsheet titled
"Charity Week — Comment Replies" with the "Replies" worksheet + header row via
the Sheets API directly (needs only the `spreadsheets` scope — no Drive scope),
then prints the id and url. Paste those into .env (CW_APPROVAL_SHEET_ID / _URL).

Pass an existing sheet id as argv[1] to just (re)write the header instead of
creating a new sheet.
"""

import sys
from googleapiclient.discovery import build
from google_auth import get_credentials
from sheets_client import HEADER, WORKSHEET


def main():
    svc = build("sheets", "v4", credentials=get_credentials(), cache_discovery=False).spreadsheets()

    if len(sys.argv) > 1:
        sheet_id = sys.argv[1]
        meta = svc.get(spreadsheetId=sheet_id).execute()
        print(f"Using existing sheet: {meta['properties']['title']}")
        # ensure the worksheet exists
        titles = [s["properties"]["title"] for s in meta["sheets"]]
        if WORKSHEET not in titles:
            svc.batchUpdate(spreadsheetId=sheet_id, body={
                "requests": [{"addSheet": {"properties": {"title": WORKSHEET}}}]
            }).execute()
    else:
        created = svc.create(body={
            "properties": {"title": "Charity Week — Comment Replies"},
            "sheets": [{"properties": {"title": WORKSHEET}}],
        }).execute()
        sheet_id = created["spreadsheetId"]
        print(f"Created sheet: {created['properties']['title']}")

    # write the header row
    svc.values().update(
        spreadsheetId=sheet_id,
        range=f"{WORKSHEET}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": [HEADER]},
    ).execute()

    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    print(f"\nCW_APPROVAL_SHEET_ID={sheet_id}")
    print(f"CW_APPROVAL_SHEET_URL={url}")
    print("\nPaste those two lines into .env. Then share the sheet (Editor) with the CW volunteers.")


if __name__ == "__main__":
    main()
