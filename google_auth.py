"""Shared Google OAuth for the CW agent — ONE user token covering YouTube + Sheets.

A single installed-app OAuth login as the contentbase1 account (manager on the
Charity Week channel) authorizes both scopes:
  - youtube.force-ssl  → read comments + post replies AS the channel
  - spreadsheets       → create/read/write the approval sheet

The token (with refresh token) is cached to TOKEN_PATH and reused by the daily
headless run. No service account — contentbase1 owns the approval sheet directly.
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/spreadsheets",
]
CLIENT_SECRET_PATH = os.environ.get("CW_GOOGLE_CLIENT_SECRET", "state/client_secret.json")
TOKEN_PATH = os.environ.get("CW_GOOGLE_TOKEN", "state/token.json")


def _bootstrap_from_env():
    """Cloud routines have no local files — materialize the OAuth JSONs from env
    vars (CW_GOOGLE_CLIENT_SECRET_JSON / CW_GOOGLE_TOKEN_JSON) if the files are
    absent. Harmless locally (files already exist)."""
    for env_key, path in (("CW_GOOGLE_CLIENT_SECRET_JSON", CLIENT_SECRET_PATH),
                          ("CW_GOOGLE_TOKEN_JSON", TOKEN_PATH)):
        blob = os.environ.get(env_key)
        if blob and not os.path.exists(path):
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w") as f:
                f.write(blob)


def get_credentials():
    """Return valid OAuth user credentials, running the one-time consent if needed.

    On first run this opens a browser. Sign in with contentbase1 and, when the
    channel picker appears, choose the **Charity Week** channel so replies post
    as the channel (not as a personal account). In the cloud, creds come from env
    vars instead (no browser) — see _bootstrap_from_env.
    """
    _bootstrap_from_env()
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds
