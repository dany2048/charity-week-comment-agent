# Daily run — orchestration (the scheduled Claude session executes this)

The "thinking" (triage + drafting) is done by Claude itself on the Max
subscription — there is NO OpenAI/Anthropic API key in this pipeline. I/O is
plain Python on free Google APIs. One contentbase1 OAuth token covers YouTube +
Sheets (`google_auth.py`).

**Current mode = HOLD FOR REVIEW.** Nothing auto-posts. Every drafted reply goes
to the Google Sheet for the CW volunteers to approve first. (Once trusted, the
zero-risk AUTO_SAFE bucket can be re-enabled for auto-send.)

## Steps

0. **Apply reviewer edits (the 'Needs Edit' loop):** `python revise_edits.py export`
   → pulls rows a reviewer marked **Needs Edit** with an instruction in "Your comments"
     into `state/edits_pending.json`. Claude rewrites each Suggested Reply per
     `cw_voice.md` + that instruction → `state/edits_revised.json`. Then
     `python revise_edits.py apply` writes the new replies back, clears the
     instruction, and resets Status to blank for re-approval.

1. **Fetch (I/O):** `python fetch_recent.py 6`
   → pulls unanswered top-level comments for ONLY the **last 6 videos** (never the
     decade-old backlog). Writes `state/comments_pending.json` (with video titles)
     and marks everything seen so it never reprocesses.

2. **Triage + draft (Claude, on subscription):**
   - Read `cw_voice.md` (voice grounded in CW's real past replies + 4-bucket policy
     + HARD RULES, incl. *only verifiable facts, never fabricate*).
   - For each comment assign a bucket (AUTO_SAFE / REVIEW / GENERIC_ONLY / SKIP)
     and draft a reply in CW voice ("JazakAllahu kheyran", "Allah swt", 🧡💙).
     SKIP → no draft, `status_default` = "Don't Answer". Substantive → blank status
     (reviewer approves).
   - Write `state/drafts.json` (schema in cw_voice.md; include video_title +
     status_default).

3. **Publish to the review sheet (I/O):**
   - First time / full rebuild: `python build_review_sheet.py`
     (formatted instructions panel on top + table + Status dropdown).
   - Daily incremental (append only new rows): `python push_drafts.py <YYYY-MM-DD>`
     in hold mode just appends to the sheet (no auto-send).

4. **Notify volunteers (manual paste by Marya):** `push_drafts.py` writes the
   ready-to-paste line to `state/nudge.txt`. Marya pastes it into the CW WhatsApp
   group (~10s). No WhatsApp automation (ban risk).

5. **Send approved (I/O), later tick:** `python send_approved.py <DATE>`
   → posts every row whose **Status = Approved** (using the possibly-edited reply
     in the sheet), marks them Posted. Safe to re-run; Posted rows are skipped.

## Scheduling
Run steps 1–4 once daily and step 5 on a later daily tick (gives volunteers a
review window). Use `/schedule` or `/loop` locally so it runs on the Max
subscription with the local OAuth token.
