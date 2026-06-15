"""One-time Meta setup: turn a short-lived USER token from the Graph API Explorer
into a long-lived PAGE token, discover the FB Page id + connected IG account id,
and write them into .env.

Usage:
  python meta_setup.py <APP_ID> <APP_SECRET> <USER_TOKEN> [page_name_substring]

If the account manages more than one Page, pass a substring of the CW page name
(e.g. "charity") to pick it.
"""

import os
import re
import sys
import requests

GV = os.environ.get("CW_META_GRAPH_VERSION", "v23.0")
BASE = f"https://graph.facebook.com/{GV}"
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

KEYS = ("CW_META_APP_ID", "CW_META_APP_SECRET", "CW_META_PAGE_TOKEN",
        "CW_FB_PAGE_ID", "CW_IG_USER_ID")


def _update_env(values):
    lines = []
    if os.path.exists(ENV_PATH):
        lines = open(ENV_PATH).read().splitlines()
    have = set()
    for i, ln in enumerate(lines):
        m = re.match(r"\s*export\s+(\w+)=", ln)
        if m and m.group(1) in values:
            lines[i] = f"export {m.group(1)}={values[m.group(1)]}"
            have.add(m.group(1))
    extra = [f"export {k}={v}" for k, v in values.items() if k not in have]
    if extra:
        lines += ["", "# --- Meta (Facebook Page + Instagram comments) ---"] + extra
    open(ENV_PATH, "w").write("\n".join(lines) + "\n")


def main():
    app_id, app_secret, user_token = sys.argv[1:4]
    name_sub = sys.argv[4].lower() if len(sys.argv) > 4 else ""

    # 1) short-lived user token -> long-lived user token
    r = requests.get(f"{BASE}/oauth/access_token", params={
        "grant_type": "fb_exchange_token", "client_id": app_id,
        "client_secret": app_secret, "fb_exchange_token": user_token}).json()
    if "access_token" not in r:
        raise SystemExit(f"Token exchange failed: {r}")
    ll_user = r["access_token"]

    # 2) list managed Pages (page tokens derived here are long-lived)
    pages = requests.get(f"{BASE}/me/accounts", params={
        "access_token": ll_user,
        "fields": "id,name,access_token,instagram_business_account{id,username}",
    }).json().get("data", [])
    if not pages:
        raise SystemExit("No Pages found for this user. Is the account a Page admin?")

    if len(pages) == 1:
        page = pages[0]
    elif name_sub:
        match = [p for p in pages if name_sub in p["name"].lower()]
        if len(match) != 1:
            raise SystemExit(f"'{name_sub}' matched {len(match)} pages: {[p['name'] for p in pages]}")
        page = match[0]
    else:
        raise SystemExit("Multiple pages — re-run with a name substring:\n  " +
                         "\n  ".join(f"{p['name']} ({p['id']})" for p in pages))

    ig = (page.get("instagram_business_account") or {})
    values = {
        "CW_META_APP_ID": app_id, "CW_META_APP_SECRET": app_secret,
        "CW_META_PAGE_TOKEN": page["access_token"], "CW_FB_PAGE_ID": page["id"],
        "CW_IG_USER_ID": ig.get("id", ""),
    }
    _update_env(values)

    print(f"Page : {page['name']} ({page['id']})")
    print(f"IG   : @{ig.get('username','?')} ({ig.get('id','— none linked!')})")
    print("Wrote CW_META_* + CW_FB_PAGE_ID + CW_IG_USER_ID to .env")
    if not ig.get("id"):
        print("\n⚠ No Instagram business account is linked to this Page. "
              "Link a Professional IG account in Page settings, then re-run.")


if __name__ == "__main__":
    main()
