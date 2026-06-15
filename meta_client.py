"""Meta Graph API client for the CW comment agent (Facebook Page + Instagram).

Comments only (no DMs — those need App Review). Mirrors youtube_client.py:
  - fetch unanswered top-level comments on the last N FB posts + IG media
  - reply to a comment on either platform, AS the Page / IG account

Auth: a long-lived Page access token (CW_META_PAGE_TOKEN). FB Page id and the
connected IG business-account id are discovered by meta_setup.py and stored in
.env. The token-holder must be a Page admin; with the app in Standard Access
that's enough to manage comments on the owned Page/IG — no App Review.
"""

import json
import os
import requests

GV = os.environ.get("CW_META_GRAPH_VERSION", "v23.0")
BASE = f"https://graph.facebook.com/{GV}"
PAGE_TOKEN = os.environ.get("CW_META_PAGE_TOKEN", "")
PAGE_ID = os.environ.get("CW_FB_PAGE_ID", "")
IG_ID = os.environ.get("CW_IG_USER_ID", "")


def _get(path, **params):
    params["access_token"] = PAGE_TOKEN
    r = requests.get(f"{BASE}/{path}", params=params, timeout=30)
    if not r.ok:
        raise SystemExit(f"GET {path} failed: {r.status_code} {r.text}")
    return r.json()


def _post(path, **data):
    data["access_token"] = PAGE_TOKEN
    r = requests.post(f"{BASE}/{path}", data=data, timeout=30)
    if not r.ok:
        raise SystemExit(f"POST {path} failed: {r.status_code} {r.text}")
    return r.json()


def fetch_fb_comments(max_posts=6):
    """Top-level comments on the Page's last `max_posts` posts.
    Returns (comments, posts). `channel_already_replied` = the Page replied in-thread.

    Comments are read as a FIELD EXPANSION on each post (`posts?fields=comments{…}`)
    rather than via the `/{post}/comments` edge — the edge trips Meta's public-content
    check on composite post ids, the expansion does not.
    """
    if not PAGE_ID:
        raise SystemExit("Set CW_FB_PAGE_ID (run meta_setup.py).")
    posts = _get(
        f"{PAGE_ID}/posts", limit=max_posts,
        fields="id,message,created_time,comments.limit(100){id,from,message,created_time,comments.limit(25){from}}",
    ).get("data", [])
    out = []
    for p in posts:
        title = (p.get("message") or "(photo/video post)")[:70]
        for cm in p.get("comments", {}).get("data", []):
            if cm.get("from", {}).get("id") == PAGE_ID:
                continue  # the Page's own comment — never reply to ourselves
            replied = any(rep.get("from", {}).get("id") == PAGE_ID
                          for rep in cm.get("comments", {}).get("data", []))
            out.append({
                "platform": "Facebook", "comment_id": cm["id"], "source": p["id"],
                "source_title": title, "author": cm.get("from", {}).get("name", ""),
                "comment_text": cm.get("message", ""), "published_at": cm.get("created_time", ""),
                "channel_already_replied": replied,
            })
    return out, posts


def fetch_ig_comments(max_media=6):
    """Top-level comments on the IG account's last `max_media` media."""
    if not IG_ID:
        raise SystemExit("Set CW_IG_USER_ID (run meta_setup.py).")
    media = _get(
        f"{IG_ID}/media", limit=max_media,
        fields="id,caption,timestamp,permalink,comments.limit(100){id,from,text,timestamp,replies.limit(25){from}}",
    ).get("data", [])
    out = []
    for m in media:
        title = (m.get("caption") or "(IG media)")[:70]
        for cm in m.get("comments", {}).get("data", []):
            if cm.get("from", {}).get("id") == IG_ID:
                continue  # our own comment — never reply to ourselves
            replied = any(rep.get("from", {}).get("id") == IG_ID
                          for rep in cm.get("replies", {}).get("data", []))
            out.append({
                "platform": "Instagram", "comment_id": cm["id"], "source": m["id"],
                "source_title": title, "author": cm.get("from", {}).get("username", ""),
                "comment_text": cm.get("text", ""), "published_at": cm.get("timestamp", ""),
                "channel_already_replied": replied,
            })
    return out, media


def reply(platform, comment_id, message):
    """Reply to a comment. FB → /{id}/comments, IG → /{id}/replies."""
    if platform == "Instagram":
        return _post(f"{comment_id}/replies", message=message)["id"]
    return _post(f"{comment_id}/comments", message=message)["id"]


# ---------------------------------------------------------------- DMs (Messenger + IG Direct)

def _actionable_dm(convo, owner_id, platform_label):
    """If the newest message in a conversation is from the OTHER party (not us),
    return a row to draft a reply to; else None (we already answered last)."""
    msgs = convo.get("messages", {}).get("data", [])
    if not msgs:
        return None
    newest = msgs[0]  # messages come newest-first
    frm = newest.get("from", {})
    if frm.get("id") == owner_id or not frm.get("id"):
        return None
    return {
        "platform": platform_label,
        "comment_id": frm["id"],                 # recipient id — what we reply TO
        "source": convo.get("id", ""),
        "source_title": f"DM from {frm.get('name') or frm.get('username') or 'user'}",
        "author": frm.get("name") or frm.get("username") or "",
        "comment_text": newest.get("message", ""),
        "published_at": newest.get("created_time", ""),
        "channel_already_replied": False,
    }


def fetch_messenger_dms(max_convos=15):
    """Open Messenger conversations whose latest message is from the user."""
    convos = _get(f"{PAGE_ID}/conversations", limit=max_convos,
                  fields="id,updated_time,messages.limit(3){from,message,created_time}").get("data", [])
    return [r for c in convos if (r := _actionable_dm(c, PAGE_ID, "Messenger"))], convos


def fetch_ig_dms(max_convos=15):
    """Open Instagram Direct conversations.

    NOTE: Instagram messaging is gated by the `instagram_manage_messages` capability
    at Advanced Access, which requires Meta App Review + Business Verification. Until
    that is granted this returns nothing (the IG-node /conversations call fails with
    "(#3) Application does not have the capability"). Messenger DMs are unaffected.
    """
    try:
        convos = _get(f"{PAGE_ID}/conversations", platform="instagram", limit=max_convos,
                      fields="id,updated_time,messages.limit(3){from,message,created_time}").get("data", [])
    except SystemExit as e:
        print(f"  ! IG DM read unavailable (needs IG messaging capability / App Review): {e}")
        return [], []
    return [r for c in convos if (r := _actionable_dm(c, IG_ID, "Instagram DM"))], convos


def send_dm(platform, recipient_id, text):
    """Send a DM reply (within the 24h window, messaging_type=RESPONSE).
    Messenger → /{PAGE_ID}/messages, IG Direct → /{IG_ID}/messages."""
    edge = f"{IG_ID}/messages" if platform == "Instagram DM" else f"{PAGE_ID}/messages"
    r = _post(edge, recipient=json.dumps({"id": recipient_id}),
              message=json.dumps({"text": text}), messaging_type="RESPONSE")
    return r.get("message_id") or r.get("id", "sent")


if __name__ == "__main__":
    fb, _ = fetch_fb_comments()
    ig, _ = fetch_ig_comments()
    print(f"FB: {len(fb)} comments, IG: {len(ig)} comments")
    for c in (fb + ig)[:6]:
        flag = " (replied)" if c["channel_already_replied"] else ""
        print(f"- [{c['platform']}] {c['author']}: {c['comment_text'][:60]}{flag}")
