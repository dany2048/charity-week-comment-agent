# Charity Week — YouTube Comment Reply Agent

Daily, hands-off comment replies for the CW YouTube channel. Claude (on your Max
subscription) drafts + triages; the CW volunteers approve a batch in a Google
Sheet; approved replies post themselves as the Charity Week channel. **Danyal is
never in the loop.**

## Who does what
- **CB (you):** own + run the pipeline. Ahmed/Marya not needed for this.
- **Claude (Max subscription):** triage + draft (no API key).
- **CW volunteers (Samim's team):** approve/edit drafts in the sheet — they own the
  religious voice, so they sign off, not us.

## The flow (once a day)
```
fetch_comments.py ─▶ comments_pending.json
        │
   Claude reads cw_voice.md + pending ─▶ drafts.json   (triage + draft, on subscription)
        │
push_drafts.py ─▶ AUTO_SAFE auto-posted  +  REVIEW/GENERIC_ONLY → Google Sheet (Pending)
        │              └▶ writes state/nudge.txt
        │
   Marya pastes nudge.txt into the CW WhatsApp group (~10s/day)
        │
   volunteers open the sheet, set Approve? = Yes (and edit text if they like)
        │
send_approved.py ─▶ posts the Yes rows, marks them Posted
```
SKIP comments are left unanswered (logged), mirroring how Samim already handles
risky comments.

## One-time setup (the only part that needs you)
1. **Python deps:** `pip install -r requirements.txt`
2. **YouTube OAuth:**
   - Google Cloud Console → new project → enable **YouTube Data API v3**.
   - Create **OAuth client → Desktop app** → download JSON → save as `state/client_secret.json`.
   - Find the **CW channel id** (UC…) and set `CW_YT_CHANNEL_ID`.
   - Sign in with the Google account that has **manager/owner** access to the CW channel
     when the browser consent opens on first run.
3. **Approval Google Sheet:**
   - Create a Sheet (or reuse the content-calendar sheet, new tab "Replies").
   - Google Cloud → create a **service account** → download JSON → `state/service_account.json`.
   - **Share the Sheet** with the service-account email (…iam.gserviceaccount.com) as Editor.
   - Set `CW_APPROVAL_SHEET_ID` to the sheet id.
4. `cp config.example.env .env` and fill in the blanks; `source .env`.

## Run / test
```bash
source .env
python youtube_client.py          # smoke test: lists visible comments
python fetch_comments.py          # → state/comments_pending.json
# (Claude drafts state/drafts.json per daily_run.md)
python push_drafts.py 2026-06-08  # auto-send safe + queue the rest to the sheet
python send_approved.py 2026-06-08  # post approved rows
```

## Scheduling (uses your Max subscription)
Run the daily flow via `/schedule` or `/loop` **locally** (needs local creds +
your subscription). See `daily_run.md` for the exact step sequence the scheduled
Claude session performs. Recommended: steps 1–4 each morning, step 5 each evening.

## Guardrails
All reply behavior is governed by `cw_voice.md`. Never auto-issue rulings, never
post unverified Arabic/ayah/hadith, default to silence on anything sectarian/
political/critical. The CW volunteers are the final gate on everything except the
zero-risk AUTO_SAFE bucket.

## Status / scope
- ✅ YouTube (this) — fully automatable on manager access.
- ⏳ Instagram + Facebook — same pattern via Meta Graph API (needs Meta app-review
  permissions); or ManyChat as a fast-path for Meta DMs.
- ✋ TikTok — no official comment-reply API; stays manual (paste → Claude drafts → post).
