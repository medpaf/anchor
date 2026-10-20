import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fakes
import adbclient as ac
import platform_support as plat

class DataDirTest(unittest.TestCase):
    def test_windows_uses_appdata(self):
        with mock.patch.object(plat, "WINDOWS", True), \
                mock.patch.dict(os.environ, {"APPDATA": r"C:\Users\me\AppData\Roaming"}):
            self.assertEqual(plat.data_dir(), Path(r"C:\Users\me\AppData\Roaming") / "Anchor")

    def test_linux_shares_the_gtk_apps_folder(self):
        with mock.patch.object(plat, "WINDOWS", False), mock.patch.dict(os.environ, {"XDG_DATA_HOME": "/x"}):
            self.assertEqual(plat.data_dir(), Path("/x/anchor"))

    def test_key_lives_in_the_data_folder(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(plat, "data_dir", return_value=Path(d)):
            self.assertEqual(ac.KeyStore().path, Path(d, "key.json"))

class FindAdbTest(unittest.TestCase):
    def test_bundled_adb_comes_first(self):
        with tempfile.TemporaryDirectory() as d:
            exe = "adb.exe" if plat.WINDOWS else "adb"
            tool = Path(d, "platform-tools", exe)
            tool.parent.mkdir()
            tool.write_text("")
            tool.chmod(0o755)
            with mock.patch.object(plat, "HERE", Path(d)), mock.patch("shutil.which", return_value="/usr/bin/adb"):
                self.assertEqual(plat.find_adb(), str(tool))

    def test_windows_looks_in_the_android_sdk(self):
        with mock.patch.object(plat, "WINDOWS", True), \
                mock.patch.dict(os.environ, {"LOCALAPPDATA": r"C:\L"}, clear=False), \
                mock.patch("shutil.which", return_value=None):
            found = plat.adb_candidates()
        self.assertTrue(all(c.endswith("adb.exe") for c in found))
        self.assertIn(os.path.join(r"C:\L", "Android", "Sdk", "platform-tools", "adb.exe"), found)

class AdbWindowTest(unittest.TestCase):
    def test_adb_runs_without_a_console_window(self):
        done = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        with mock.patch("subprocess.run", return_value=done) as run:
            ac.Adb("adb").run(["devices"])
        self.assertEqual(run.call_args.kwargs["creationflags"], plat.NO_WINDOW)

    def test_adb_doesnt_search_the_network(self):

        done = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        with mock.patch("subprocess.run", return_value=done) as run:
            ac.Adb("adb").run(["devices"])
        self.assertEqual(run.call_args.kwargs["env"]["ADB_MDNS"], "0")
        self.assertIn("PATH", run.call_args.kwargs["env"], "the rest of the environment is kept")

class MachineIdTest(unittest.TestCase):
    def test_free_version_uses_the_platforms_id(self):
        with mock.patch.object(plat, "machine_id", return_value="guid-123"):
            self.assertEqual(ac.machine_id(), "guid-123")

class UpdateTest(unittest.TestCase):
    def test_only_the_installed_app_updates_itself(self):
        self.assertFalse(plat.installed_by_installer(), "not when run from source")
        with tempfile.TemporaryDirectory() as d, mock.patch.object(plat, "WINDOWS", True), \
                mock.patch.object(plat.sys, "frozen", True, create=True), \
                mock.patch.object(plat.sys, "executable", str(Path(d, "Anchor.exe"))):
            self.assertFalse(plat.installed_by_installer(), "not without the installer's uninstaller")
            Path(d, "unins000.exe").write_text("")
            self.assertTrue(plat.installed_by_installer())

    def test_the_installer_runs_silently_and_reopens_anchor(self):
        with mock.patch.object(plat.subprocess, "DETACHED_PROCESS", 8, create=True), \
                mock.patch.object(plat.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, create=True), \
                mock.patch.object(plat.subprocess, "Popen") as popen:
            plat.run_update_installer("C:/Temp/anchor-win.exe")
        args = popen.call_args[0][0]
        self.assertEqual(args[0], "C:/Temp/anchor-win.exe")
        self.assertIn("/VERYSILENT", args)
        self.assertIn("/UPDATE=1", args, "the installer opens the new version")
        self.assertEqual(popen.call_args.kwargs["creationflags"], 8 | 512, "it outlives Anchor")

class WindowsOnlyTest(unittest.TestCase):
    def test_title_bar_and_app_id_do_nothing_elsewhere(self):
        with mock.patch.object(plat, "WINDOWS", False):
            plat.style_title_bar(0)
            plat.set_app_id()

    def test_texts_name_windows_tools(self):
        with mock.patch.object(plat, "WINDOWS", True):
            self.assertIn("platform-tools", plat.adb_install_hint())
            self.assertNotIn("apt", plat.password_missing_text())

if __name__ == "__main__":
    unittest.main()
