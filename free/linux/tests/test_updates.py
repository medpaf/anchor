import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fakes
import updates

class UpdatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(updates, "HERE", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def built_from(self, commit):
        Path(self.tmp.name, "build-commit").write_text(commit + "\n")

    def github_says(self, commit):
        body = json.dumps({"ref": "refs/tags/linux", "object": {"sha": commit, "type": "commit"}}).encode()
        return mock.patch.object(updates.urllib.request, "urlopen", return_value=io.BytesIO(body))

    def test_same_commit_is_up_to_date(self):
        self.built_from("abc123")
        with self.github_says("abc123"):
            self.assertEqual(updates.check("linux"), updates.CURRENT)

    def test_different_commit_means_a_new_version(self):
        self.built_from("abc123")
        with self.github_says("def456"):
            self.assertEqual(updates.check("linux"), updates.AVAILABLE)

    def test_a_copy_not_built_by_github_cant_tell(self):
        with mock.patch.object(updates.urllib.request, "urlopen") as urlopen:
            self.assertEqual(updates.check("linux"), updates.UNKNOWN)
        urlopen.assert_not_called()

    def test_asks_for_the_right_release_and_sends_nothing_else(self):
        self.built_from("abc123")
        with self.github_says("abc123") as urlopen:
            updates.check("windows")
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "https://api.github.com/repos/medpaf/anchor/git/ref/tags/windows")
        self.assertIsNone(request.data, "a plain GET: no data is sent")

    def test_no_internet_is_reported(self):
        self.built_from("abc123")
        with mock.patch.object(updates.urllib.request, "urlopen", side_effect=updates.urllib.error.URLError("offline")):
            with self.assertRaises(OSError):
                updates.check("linux")

    def test_a_strange_answer_is_reported(self):
        self.built_from("abc123")
        with mock.patch.object(updates.urllib.request, "urlopen", return_value=io.BytesIO(b'{"message": "Not Found"}')):
            with self.assertRaises(OSError):
                updates.check("linux")

    def test_download_saves_the_package(self):
        body = b"!<arch>\n" + b"x" * 1000
        with mock.patch.object(updates.urllib.request, "urlopen", return_value=io.BytesIO(body)) as urlopen:
            path = updates.download("linux", "anchor-linux.deb")
        self.addCleanup(lambda: (path.unlink(), path.parent.rmdir()))
        self.assertEqual(path.read_bytes(), body)
        self.assertEqual(urlopen.call_args[0][0].full_url,
                         "https://github.com/medpaf/anchor/releases/download/linux/anchor-linux.deb")
        if os.name != "nt":
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700, "a private folder")

    def test_download_refuses_something_that_isnt_a_package(self):
        with mock.patch.object(updates.urllib.request, "urlopen", return_value=io.BytesIO(b"<html>Not Found</html>")):
            with mock.patch("tempfile.mkdtemp", return_value=self.tmp.name):
                with self.assertRaises(OSError):
                    updates.download("linux", "anchor-linux.deb")

    def test_download_refuses_a_windows_file_that_isnt_a_program(self):
        with mock.patch.object(updates.urllib.request, "urlopen", return_value=io.BytesIO(b"<html>Not Found</html>")):
            with mock.patch("tempfile.mkdtemp", return_value=self.tmp.name):
                with self.assertRaises(OSError):
                    updates.download("windows", "anchor-win.exe")

    def test_download_pages(self):
        self.assertEqual(updates.download_page("linux"), "https://github.com/medpaf/anchor/releases/tag/linux")
        self.assertEqual(updates.download_page("windows"), "https://github.com/medpaf/anchor/releases/tag/windows")

if __name__ == "__main__":
    unittest.main()
