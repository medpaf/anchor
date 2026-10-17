"""Unit tests for desktop/catalog.py (the Never allow defaults and link parsing)."""

import unittest

from fakes import ROOT  # noqa: F401  (puts desktop/ on sys.path)
import catalog


class DefaultsTest(unittest.TestCase):
    def test_social_media_is_blocked_by_default(self):
        names = {a["name"] for a in catalog.defaults()}
        for expected in ("TikTok", "Instagram", "Reddit", "YouTube", "Facebook", "Snapchat",
                         "X (Twitter)", "Threads"):
            self.assertIn(expected, names)

    def test_messaging_apps_stay_allowed(self):
        pkgs = {a["pkg"] for a in catalog.defaults()}
        for messaging in ("com.facebook.orca",  # Messenger
                          "com.facebook.mlite",  # Messenger Lite
                          "com.whatsapp", "org.thoughtcrime.securesms", "org.telegram.messenger"):
            self.assertNotIn(messaging, pkgs)
        self.assertIn("com.facebook.katana", pkgs, "Facebook itself is blocked")

    def test_suggestions_dont_repeat_defaults(self):
        self.assertFalse({p for p, _ in catalog.SOCIAL} & {p for p, _ in catalog.SUGGESTIONS})


class ParseTest(unittest.TestCase):
    def test_package_names(self):
        self.assertEqual(catalog.parse_app(" com.instagram.android "), "com.instagram.android")

    def test_play_store_links(self):
        for link in ("https://play.google.com/store/apps/details?id=com.zhiliaoapp.musically",
                     "play.google.com/store/apps/details?id=com.zhiliaoapp.musically&hl=pt_PT",
                     "https://play.google.com/store/apps/details?hl=en&id=com.zhiliaoapp.musically"):
            with self.subTest(link=link):
                self.assertEqual(catalog.parse_app(link), "com.zhiliaoapp.musically")

    def test_rejects_other_text(self):
        for bad in ("instagram", "https://play.google.com/store/apps", "com.", "rm -rf /", ""):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                catalog.parse_app(bad)

    def test_names(self):
        self.assertEqual(catalog.name_for("com.instagram.android"), "Instagram")
        self.assertEqual(catalog.name_for("org.example", {"org.example": "Example"}), "Example")
        self.assertEqual(catalog.name_for("org.unknown"), "org.unknown")


if __name__ == "__main__":
    unittest.main()
