"""Unit tests for desktop/keysheet.py (the printable backup key page)."""

import unittest
from datetime import datetime

from fakes import ROOT  # noqa: F401  (puts desktop/ on sys.path)
import keysheet

KEY = "ABCD-EFGH-IJKL-MNOP-QRST-UVWX-YZ23-4567"


class KeySheetTest(unittest.TestCase):
    def test_the_page_has_the_key_and_how_to_use_it(self):
        items = keysheet.page(KEY, "Google Pixel 8", now=datetime(2026, 10, 9))
        self.assertEqual(items[0], ("title", "Anchor backup key"))
        self.assertEqual(items[1], ("key", KEY))
        text = " ".join(t for _s, t in items)
        self.assertIn("Saved on 9 October 2026", text)
        self.assertIn("paired with Google Pixel 8", text)
        self.assertIn("Use a backup key", text)
        self.assertIn("factory reset", text)

    def test_no_phone_no_mention(self):
        self.assertNotIn("paired with", keysheet.page(KEY)[2][1])


if __name__ == "__main__":
    unittest.main()
