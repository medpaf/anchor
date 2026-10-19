"""Unit tests for desktop/catalog.py (the Never allow suggestions and link parsing)."""

import unittest

from fakes import ROOT  # noqa: F401  (puts desktop/ on sys.path)
import catalog


class SuggestionsTest(unittest.TestCase):
    def test_social_media_is_suggested(self):
        names = {name for _pkg, name in catalog.SOCIAL}
        for expected in ("TikTok", "Instagram", "Reddit", "YouTube", "Facebook", "Snapchat",
                         "X (Twitter)", "Threads"):
            self.assertIn(expected, names)

    def test_messaging_apps_arent_suggested_as_social_media(self):
        pkgs = {pkg for pkg, _name in catalog.SOCIAL}
        for messaging in ("com.facebook.orca",  # Messenger
                          "com.facebook.mlite",  # Messenger Lite
                          "com.whatsapp", "org.thoughtcrime.securesms", "org.telegram.messenger"):
            self.assertNotIn(messaging, pkgs)
        self.assertIn("com.facebook.katana", pkgs, "Facebook itself is suggested")

    def test_suggestions_dont_repeat_social_media(self):
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
