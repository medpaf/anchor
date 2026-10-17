"""Well-known apps for the 'Never allow' list."""

import re
from urllib.parse import parse_qs, urlparse

# On the 'Never allow' list by default. Messaging apps (Messenger, WhatsApp, Signal…) are left out on
# purpose: Messenger is a separate app from Facebook (com.facebook.orca), so it stays allowed.
SOCIAL = [
    ("com.zhiliaoapp.musically", "TikTok"),
    ("com.ss.android.ugc.trill", "TikTok (Asia)"),
    ("com.zhiliaoapp.musically.go", "TikTok Lite"),
    ("com.instagram.android", "Instagram"),
    ("com.instagram.barcelona", "Threads"),
    ("com.facebook.katana", "Facebook"),
    ("com.facebook.lite", "Facebook Lite"),
    ("com.reddit.frontpage", "Reddit"),
    ("com.google.android.youtube", "YouTube"),
    ("com.snapchat.android", "Snapchat"),
    ("com.twitter.android", "X (Twitter)"),
    ("com.pinterest", "Pinterest"),
    ("com.tumblr", "Tumblr"),
    ("com.bereal.ft", "BeReal"),
]

# Offered in the "Add" dialog, not blocked by default.
SUGGESTIONS = [
    ("xyz.blueskyweb.app", "Bluesky"),
    ("com.linkedin.android", "LinkedIn"),
    ("tv.twitch.android.app", "Twitch"),
    ("com.discord", "Discord"),
    ("com.ninegag.android.app", "9GAG"),
    ("com.netflix.mediaclient", "Netflix"),
    ("com.disney.disneyplus", "Disney+"),
    ("com.amazon.avod.thirdpartyclient", "Prime Video"),
    ("com.tinder", "Tinder"),
]

KNOWN = dict(SOCIAL + SUGGESTIONS)

_PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+")


def defaults():
    return [{"pkg": pkg, "name": name} for pkg, name in SOCIAL]


def parse_app(text):
    """A package name from what the user typed: a package name or a Play Store link.
    Raises ValueError when it's neither."""
    text = text.strip()
    if "://" in text or text.startswith("play.google.com"):
        url = urlparse(text if "://" in text else "https://" + text)
        ids = parse_qs(url.query).get("id")
        if not ids:
            raise ValueError("That link doesn't name an app. Play Store links look like "
                             "play.google.com/store/apps/details?id=com.example.app")
        text = ids[0]
    if not _PACKAGE.fullmatch(text):
        raise ValueError("Paste a Play Store link, or a package name like com.instagram.android.")
    return text


def name_for(pkg, installed_labels=None):
    if pkg in KNOWN:
        return KNOWN[pkg]
    if installed_labels and pkg in installed_labels:
        return installed_labels[pkg]
    return pkg
