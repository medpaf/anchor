import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from fakes import data_env, placeholder_package
import placeholder

SDK = Path(os.environ.get("ANDROID_HOME") or os.path.expanduser("~/Android/Sdk"))

def build_tool(name):
    tools = sorted((SDK / "build-tools").glob(f"*/{name}")) if (SDK / "build-tools").exists() else []
    return tools[-1] if tools else None

class PlaceholderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, data_env(self.tmp.name))
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_names_the_blocked_app(self):
        for pkg in ("com.reddit.frontpage", "com.zhiliaoapp.musically", "x.y"):
            with self.subTest(pkg=pkg):
                path = placeholder.write_apk(pkg, self.tmp.name)
                self.assertEqual(placeholder_package(path), pkg)

    def test_signed_with_a_key_made_once(self):
        placeholder.build_apk("com.reddit.frontpage")
        key, cert = placeholder.ensure_key()
        if os.name != "nt":
            self.assertEqual(oct(os.stat(key).st_mode & 0o777), "0o600")
        first = cert.read_bytes()
        placeholder.build_apk("com.instagram.android")
        self.assertEqual(cert.read_bytes(), first, "the same key signs every placeholder")

    @unittest.skipUnless(shutil.which("openssl"), "checked with openssl")
    def test_signature_matches_the_contents(self):
        path = placeholder.write_apk("com.reddit.frontpage", self.tmp.name)
        with zipfile.ZipFile(path) as z:
            sf, sig = z.read("META-INF/ANCHOR.SF"), z.read("META-INF/ANCHOR.RSA")
        _, cert = placeholder.ensure_key()
        sf_path, sig_path = Path(self.tmp.name, "a.sf"), Path(self.tmp.name, "a.rsa")
        sf_path.write_bytes(sf)
        sig_path.write_bytes(sig)
        p = subprocess.run(["openssl", "cms", "-verify", "-binary", "-inform", "DER", "-in", str(sig_path),
                            "-content", str(sf_path), "-noverify", "-out", os.devnull], capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr.decode())

    @unittest.skipUnless(build_tool("apksigner") and shutil.which("java"), "needs the Android SDK and a JDK")
    def test_android_accepts_the_apk(self):
        path = placeholder.write_apk("com.reddit.frontpage", self.tmp.name)
        p = subprocess.run([str(build_tool("apksigner")), "verify", "--min-sdk-version", "24", str(path)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        dump = subprocess.run([str(build_tool("aapt2")), "dump", "badging", str(path)], capture_output=True, text=True)
        self.assertIn("package: name='com.reddit.frontpage'", dump.stdout)
        self.assertIn("application: label='Blocked by Anchor'", dump.stdout)

    def test_needs_no_openssl(self):

        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            apk = placeholder.build_apk("com.reddit.frontpage")
        self.assertTrue(apk.startswith(b"PK"))

if __name__ == "__main__":
    unittest.main()
