import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from fakes import ROOT, ac

SERIAL = os.environ.get("ANCHOR_TEST_SERIAL")
APK = ROOT / "desktop" / "anchor-agent.apk"
DEFAULT_TARGETS = ["com.android.camera2", "com.android.gallery3d", "com.android.deskclock", "com.android.contacts"]
PROTECTED = "com.android.dialer"
LAUNCHER_QUERY = ("cmd package query-activities --brief "
                  "-a android.intent.action.MAIN -c android.intent.category.LAUNCHER")

@unittest.skipUnless(SERIAL, "set ANCHOR_TEST_SERIAL to run device tests")
class DeviceTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not SERIAL.startswith("emulator-") and os.environ.get("ANCHOR_TEST_ALLOW_REAL_PHONE") != "1":
            raise unittest.SkipTest(f"{SERIAL} isn't an emulator; set ANCHOR_TEST_ALLOW_REAL_PHONE=1 to allow it")
        if not APK.exists():
            raise unittest.SkipTest("build the APK first: android/build.sh")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.env = mock.patch.dict(os.environ, {"XDG_DATA_HOME": cls.tmp.name})
        cls.env.start()
        path = ac.find_adb()
        if not path:
            raise unittest.SkipTest("adb not found")
        cls.adb = ac.Adb(path)
        cls.agent = ac.Agent(cls.adb, SERIAL)
        cls.token = ac.KeyStore().token
        if cls.agent.installed():
            raise unittest.SkipTest("Anchor is already on this device; use a freshly wiped emulator")
        targets = os.environ.get("ANCHOR_TEST_APPS", ",".join(DEFAULT_TARGETS)).split(",")
        cls.targets = sorted(p for p in targets if cls.installed(p))
        if len(cls.targets) < 2:
            raise unittest.SkipTest(f"need at least 2 of these apps installed: {targets}")

    @classmethod
    def tearDownClass(cls):
        try:
            if cls.agent.installed():
                try:
                    cls.agent.release(cls.token)
                except (ac.AgentError, ac.AdbError):
                    pass
                cls.agent.uninstall()
        finally:
            cls.env.stop()
            cls.tmp.cleanup()

    @classmethod
    def sh(cls, cmd, timeout=60):
        return cls.agent.shell(cmd, timeout=timeout).strip()

    @classmethod
    def installed(cls, pkg):
        return f"package:{pkg}" in cls.sh(f"pm list packages -u {pkg}")

    def state(self, pkg):

        line = next((l for l in self.sh(f"dumpsys package {pkg}").splitlines()
                     if l.strip().startswith("User 0:") and "installed=" in l), "")
        return {k: f"{k}=true" in line for k in ("installed", "hidden", "suspended")}

    def assertBlocked(self, pkg):
        s = self.state(pkg)
        self.assertTrue(s["installed"] and s["hidden"] and s["suspended"], f"{pkg} not blocked: {s}")

    def assertFree(self, pkg):
        s = self.state(pkg)
        self.assertTrue(s["installed"] and not s["hidden"] and not s["suspended"], f"{pkg} still blocked: {s}")

    def assertAgentError(self, code, fn, *args):
        with self.assertRaises(ac.AgentError) as cm:
            fn(*args)
        self.assertEqual(cm.exception.code, code)

    def wait_for_boot(self, timeout=240):
        self.adb.run(["wait-for-device"], serial=SERIAL, timeout=timeout)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.sh("getprop sys.boot_completed") == "1":
                return
            time.sleep(2)
        self.fail("device didn't finish booting")

    def test_01_install(self):
        self.agent.install(APK)
        st = self.agent.status(self.token)
        self.assertEqual(st["version"], ac.AGENT_VERSION)
        self.assertFalse(st["owner"] or st["paired"] or st["shifted"])

    def test_02_nothing_works_before_device_owner(self):
        self.assertAgentError("not_owner", self.agent.pair, self.token)
        self.assertAgentError("not_owner", self.agent.shift, self.token, self.targets)

    def test_03_become_device_owner(self):
        self.agent.set_device_owner()
        self.assertTrue(self.agent.status(self.token)["owner"])

    def test_04_pair_once(self):
        st = self.agent.pair(self.token)
        self.assertTrue(st["paired"] and st["authorized"])
        self.assertAgentError("already_paired", self.agent.pair, "f" * 32)
        self.assertFalse(self.agent.status("f" * 32)["authorized"])

    def test_05_lists_apps_with_icons(self):
        apps, icons = self.agent.apps()
        pkgs = {a["pkg"] for a in apps}
        for p in self.targets:
            self.assertIn(p, pkgs)
            self.assertTrue(icons[p].startswith(b"\x89PNG"))
        self.assertNotIn(ac.AGENT_PKG, pkgs)

    def test_06_shift_hides_and_suspends(self):
        selection = self.targets + ([PROTECTED] if self.installed(PROTECTED) else [])
        st = self.agent.shift(self.token, selection)
        self.assertTrue(st["shifted"])
        self.assertEqual(st["blocked"], self.targets)
        if self.installed(PROTECTED):
            self.assertEqual(st["failed"], [PROTECTED])
        launcher = self.sh(LAUNCHER_QUERY)
        for p in self.targets:
            self.assertBlocked(p)
            self.assertNotIn(p, launcher)

    def test_07_hidden_apps_stay_in_desktop_list(self):
        apps, icons = self.agent.apps()
        pkgs = {a["pkg"] for a in apps}
        for p in self.targets:
            self.assertIn(p, pkgs)
            self.assertIn(p, icons)

    def test_08_cannot_launch_blocked_app(self):
        p = self.targets[0]
        self.sh(f"monkey -p {p} -c android.intent.category.LAUNCHER 1")
        time.sleep(2)
        self.assertNotIn(p, self.sh("dumpsys activity activities | grep -m1 topResumedActivity"))
        self.assertNotIn(p, self.sh("pidof " + p + " || true"))

    def test_09_adb_bypasses_fail(self):
        p = self.targets[0]
        attempts = [
            f"pm unhide {p}",
            f"pm unsuspend {p}",
            f"pm install-existing {p}",
            f"pm enable {p}",
            f"pm uninstall --user 0 {p}",
            f"pm uninstall {p}",
        ]
        for cmd in attempts:
            with self.subTest(cmd=cmd):
                self.sh(cmd)
                self.assertBlocked(p)

    def test_10_reinstalling_the_apk_fails_to_unblock(self):
        p = self.targets[1]
        code_path = next(l.split("codePath=")[1].strip()
                         for l in self.sh(f"dumpsys package {p}").splitlines() if "codePath=" in l)
        remote = self.sh(f"ls {code_path}/*.apk").splitlines()[0]
        with tempfile.TemporaryDirectory() as d:
            local = Path(d, "app.apk")
            self.adb.run(["pull", remote, str(local)], serial=SERIAL, timeout=120)
            self.assertTrue(local.exists())
            self.adb.run(["install", "-r", str(local)], serial=SERIAL, timeout=180)
        self.assertBlocked(p)

    def test_11_cannot_remove_or_disable_anchor(self):
        attempts = [
            f"pm clear {ac.AGENT_PKG}",
            f"pm disable-user --user 0 {ac.AGENT_PKG}",
            f"pm uninstall {ac.AGENT_PKG}",
            f"dpm remove-active-admin {ac.AGENT_ADMIN}",
        ]
        for cmd in attempts:
            with self.subTest(cmd=cmd):
                self.sh(cmd)
                st = self.agent.status(self.token)
                self.assertTrue(st["owner"] and st["authorized"] and st["shifted"], st)
                self.assertBlocked(self.targets[0])
        self.assertNotIn("Success", self.sh("pm create-user --guest anchor-test"))

    def test_12_wrong_key_cannot_unshift(self):
        bad = "0" * 32
        self.assertAgentError("bad_key", self.agent.unshift, bad)
        self.assertAgentError("bad_key", self.agent.select, bad, [])
        self.assertAgentError("bad_key", self.agent.release, bad)
        self.assertTrue(self.agent.status(self.token)["shifted"])
        self.assertBlocked(self.targets[0])

    def test_13_recheck_job_is_scheduled(self):
        self.assertIn(ac.AGENT_PKG, self.sh(f"dumpsys jobscheduler {ac.AGENT_PKG} | grep -m1 JOB"))

    def test_14_survives_reboot(self):
        if os.environ.get("ANCHOR_TEST_FAST") == "1":
            self.skipTest("ANCHOR_TEST_FAST=1")
        self.adb.run(["reboot"], serial=SERIAL, timeout=60)
        time.sleep(5)
        self.wait_for_boot()
        st = self.agent.status(self.token)
        self.assertTrue(st["owner"] and st["shifted"])
        for p in self.targets:
            self.assertBlocked(p)

    def test_15_update_keeps_device_owner_and_state(self):
        self.agent.install(APK)
        st = self.agent.status(self.token)
        self.assertTrue(st["owner"] and st["authorized"] and st["shifted"])
        self.assertEqual(st["blocked"], self.targets)

    def test_16_shrinking_list_while_shifted(self):
        keep, freed = self.targets[0], self.targets[1:]
        st = self.agent.select(self.token, [keep])
        self.assertEqual(st["blocked"], [keep])
        self.assertBlocked(keep)
        for p in freed:
            self.assertFree(p)

    def test_17_unshift_brings_everything_back(self):
        self.agent.select(self.token, self.targets)
        st = self.agent.unshift(self.token)
        self.assertFalse(st["shifted"])
        self.assertEqual(st["blocked"], [])
        launcher = self.sh(LAUNCHER_QUERY)
        for p in self.targets:
            self.assertFree(p)
            self.assertIn(p, launcher)
        self.assertNotIn(ac.AGENT_PKG, self.sh(f"dumpsys jobscheduler {ac.AGENT_PKG} | grep -m1 JOB") or "")

    def phone_clock(self):

        dow, hhmm, sec = self.sh("date +%u_%H:%M_%S").split("_")
        h, m = hhmm.split(":")
        return int(dow), int(h) * 60 + int(m), int(sec)

    def wait_until(self, cond, timeout, what):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if cond():
                return
            time.sleep(3)
        self.fail(f"timed out after {timeout}s waiting for {what}")

    def blocked_now(self):
        return all(self.state(p)["hidden"] for p in self.targets)

    def free_now(self):
        return all(not self.state(p)["hidden"] and not self.state(p)["suspended"] for p in self.targets)

    def clock_locked(self):

        return "no_config_date_time" in self.sh("dumpsys user")

    def schedule_at(self, start_min, end_min, dow, packages):
        hhmm = lambda m: f"{(m // 60) % 24:02d}:{m % 60:02d}"
        return [{"id": "t1", "name": "Test", "enabled": True, "days": [dow], "packages": packages,
                 "start": hhmm(start_min % 1440), "end": hhmm(end_min % 1440)}]

    def only_first_hidden(self):
        first, rest = self.targets[0], self.targets[1:]
        return self.state(first)["hidden"] and all(not self.state(p)["hidden"] for p in rest)

    def first_free(self):
        return not self.state(self.targets[0])["hidden"] and not self.state(self.targets[0])["suspended"]

    def test_17b_timed_shift_ends_by_itself(self):
        self.agent.allow_background()
        st = self.agent.shift(self.token, self.targets, minutes=1)
        self.assertEqual(st["mode"], "timer")
        self.assertTrue(st["exact_alarms"], "the phone should be allowed to wake exactly")
        self.assertTrue(self.blocked_now())
        self.wait_until(self.free_now, 120, "the 1-minute timer to end")
        self.assertIsNone(self.agent.status(self.token)["mode"])

    def test_17c_app_schedule_starts_and_ends_by_itself(self):
        dow, now_min, sec = self.phone_clock()
        if sec > 40 or now_min >= 1436:
            time.sleep(62 - sec)
            dow, now_min, sec = self.phone_clock()
        start = now_min + 1
        st = self.agent.set_schedules(self.token, self.schedule_at(start, start + 1, dow, [self.targets[0]]))
        self.assertEqual(st["scheduled_now"], {})
        self.assertTrue(self.free_now())
        self.wait_until(self.only_first_hidden, 120, "the app's schedule to start")
        st = self.agent.status(self.token)
        self.assertEqual(list(st["scheduled_now"]), [self.targets[0]])
        self.assertFalse(st["shifted"], "a schedule hides its own app, it doesn't anchor the list")
        self.wait_until(self.free_now, 120, "the app's schedule to end")
        self.agent.set_schedules(self.token, [])

    def test_17d_unshift_pauses_the_active_schedule(self):
        dow, now_min, _ = self.phone_clock()
        if now_min < 2 or now_min > 1430:
            self.skipTest("too close to midnight for a same-day window")
        st = self.agent.set_schedules(self.token, self.schedule_at(now_min - 1, now_min + 5, dow, [self.targets[0]]))
        self.assertEqual(list(st["scheduled_now"]), [self.targets[0]])
        self.assertTrue(self.only_first_hidden())
        self.assertTrue(self.clock_locked(), "date/time settings should be locked while a schedule is on")
        self.assertEqual(self.sh("settings get global auto_time"), "1")
        st = self.agent.unshift(self.token)
        self.assertEqual(st["scheduled_now"], {})
        self.assertGreater(st["paused"]["t1"], st["now"])
        self.assertTrue(self.free_now())

        st = self.agent.select(self.token, self.targets)
        self.assertEqual(st["scheduled_now"], {})
        self.assertTrue(self.free_now())
        self.agent.set_schedules(self.token, [])
        self.assertFalse(self.clock_locked(), "the clock unlocks once no schedule is on")

    DUMMY = "app.anchor.testdummy"

    def dummy_blocked(self):
        s = self.state(self.DUMMY)
        return s["installed"] and s["hidden"] and s["suspended"]

    def install_dummy_output(self):
        _, out = self.adb.run(["install", "-r", str(ROOT / "tests" / "fixtures" / "dummy.apk")],
                              serial=SERIAL, timeout=120)
        return out

    def dummy_gone(self):
        return not self.installed(self.DUMMY)

    def test_17e_placeholder_stops_the_install(self):
        self.assertFalse(self.installed(self.DUMMY))
        st = self.agent.set_install_blocks(self.token, [{"pkg": self.DUMMY, "name": "Test app"}])
        self.assertEqual(st["install_missing"], [self.DUMMY])
        self.agent.install_placeholder(self.DUMMY)
        self.assertTrue(self.state(self.DUMMY)["hidden"], "the placeholder is hidden right after it's installed")
        st = self.agent.status(self.token)
        self.assertEqual(st["install_placeholders"], [self.DUMMY])
        self.assertEqual((st["install_missing"], st["install_caught"]), ([], []))
        self.assertNotIn(self.DUMMY, st["blocked"], "placeholders aren't reported as hidden apps")
        out = self.install_dummy_output()
        self.assertIn("INSTALL_FAILED_UPDATE_INCOMPATIBLE", out, "Android refuses the real app")
        self.assertNotIn("Success", self.sh(f"pm uninstall {self.DUMMY}"), "the placeholder can't be removed")
        self.assertNotIn("Test app is blocked", self.sh("dumpsys notification --noredact"))

    def test_17f_release_removes_the_placeholder(self):
        self.agent.set_install_blocks(self.token, [])
        self.wait_until(self.dummy_gone, 30, "the placeholder to be uninstalled")
        self.assertIn("Success", self.install_dummy_output(), "the real app installs again")
        self.assertFalse(self.state(self.DUMMY)["hidden"])

    def test_17g_installed_app_is_left_alone_until_uninstalled(self):
        st = self.agent.set_install_blocks(self.token, [{"pkg": self.DUMMY, "name": "Test app"}])
        self.assertEqual(st["install_kept"], [self.DUMMY])
        self.assertFalse(self.state(self.DUMMY)["hidden"], "already installed: never touched")
        self.assertIn("Success", self.sh(f"pm uninstall {self.DUMMY}"))
        self.assertEqual(self.agent.status(self.token)["install_missing"], [self.DUMMY])
        self.agent.install_placeholder(self.DUMMY)
        self.assertIn("INSTALL_FAILED_UPDATE_INCOMPATIBLE", self.install_dummy_output())
        self.agent.set_install_blocks(self.token, [])
        self.wait_until(self.dummy_gone, 30, "the placeholder to be uninstalled")

    def test_17h_without_placeholder_it_is_hidden_and_can_be_uninstalled(self):
        st = self.agent.set_install_blocks(self.token, [{"pkg": self.DUMMY, "name": "Test app"}])
        started = time.monotonic()
        self.assertIn("Success", self.install_dummy_output())
        self.wait_until(self.dummy_blocked, 90, "the never-allowed app to be hidden after install")
        print(f"\n    fallback: hidden {time.monotonic() - started:.1f}s after install", end=" ")
        st = self.agent.status(self.token)
        self.assertEqual(st["install_caught"], [self.DUMMY])
        self.assertIn("Test app is blocked", self.sh("dumpsys notification --noredact"))
        self.assertNotIn("Success", self.sh(f"pm uninstall {self.DUMMY}"), "can't be uninstalled to escape")
        self.agent.uninstall_blocked(self.token, self.DUMMY)
        self.wait_until(self.dummy_gone, 30, "the app to be uninstalled on request")
        self.assertEqual(self.agent.status(self.token)["install_missing"], [self.DUMMY])
        self.agent.set_install_blocks(self.token, [])

    def test_17i_anchored_app_cant_be_installed_while_anchored(self):
        self.assertFalse(self.installed(self.DUMMY))
        st = self.agent.shift(self.token, self.targets[:1] + [self.DUMMY])
        self.assertEqual(st["mode"], "manual")
        self.assertIn("Success", self.install_dummy_output())
        self.wait_until(self.dummy_blocked, 90, "the anchored app to be hidden after install")
        self.agent.unshift(self.token)
        self.assertFalse(self.state(self.DUMMY)["hidden"])
        self.agent.select(self.token, self.targets)
        self.assertIn("Success", self.sh(f"pm uninstall {self.DUMMY}"))

    PERMS = ("android.permission.CAMERA", "android.permission.ACCESS_COARSE_LOCATION")

    def permission(self, perm):

        for line in self.sh(f"dumpsys package {self.DUMMY}").splitlines():
            line = line.strip()
            if line.startswith(perm + ": granted="):
                return "granted=true" in line, "POLICY_FIXED" in line
        return False, False

    def test_17j_blocked_apps_lose_their_permissions_until_released(self):
        self.assertIn("Success", self.install_dummy_output())
        for perm in self.PERMS:
            self.sh(f"pm grant {self.DUMMY} {perm}")
            self.assertEqual(self.permission(perm), (True, False), perm)
        self.agent.shift(self.token, self.targets + [self.DUMMY])
        self.assertTrue(self.dummy_blocked())
        for perm in self.PERMS:

            self.assertEqual(self.permission(perm), (False, True), f"{perm} removed and locked")
        removed = self.agent.status(self.token)["permissions_removed"]
        self.assertEqual(removed[self.DUMMY], 2)
        self.assertGreater(removed.get("com.android.camera2", 0), 0, "the Camera app lost its permissions too")
        self.agent.unshift(self.token)
        for perm in self.PERMS:
            self.assertEqual(self.permission(perm), (True, False), f"{perm} given back, and the user controls it again")
        self.assertEqual(self.agent.status(self.token)["permissions_removed"], {})
        self.agent.select(self.token, self.targets)
        self.assertIn("Success", self.sh(f"pm uninstall {self.DUMMY}"))

    def test_17k_releasing_the_last_app_stops_anchoring(self):
        st = self.agent.shift(self.token, self.targets)
        self.assertEqual(st["mode"], "manual")
        st = self.agent.select(self.token, [])
        st = self.agent.end_anchoring(self.token)
        self.assertEqual((st["mode"], st["selected"], st["blocked"]), (None, [], []))
        self.assertTrue(self.free_now())

    def test_17l_uninstall_button(self):
        self.assertIn("Success", self.install_dummy_output())
        self.agent.uninstall_app(self.token, self.DUMMY)
        self.wait_until(self.dummy_gone, 30, "the app to be uninstalled")
        with self.assertRaises(ac.AgentError) as cm:
            self.agent.uninstall_app(self.token, self.targets[0])
        self.assertEqual(cm.exception.code, "bad_request")
        self.assertTrue(self.installed(self.targets[0]))
        with self.assertRaises(ac.AgentError):
            self.agent.uninstall_app("0" * 32, self.targets[0])

    def test_17m_app_details_and_permission_switches(self):
        self.assertIn("Success", self.install_dummy_output())
        info = self.agent.app_info(self.DUMMY)
        self.assertEqual(info["label"], "Anchor test app")
        self.assertFalse(info["system"])
        perms = {p["name"]: p for p in info["permissions"]}
        self.assertEqual(set(perms), set(self.PERMS))
        self.assertTrue(all(p["label"] for p in perms.values()), "Android's own names come along")
        cam = "android.permission.CAMERA"
        info = self.agent.set_permission(self.token, self.DUMMY, cam, True)
        self.assertEqual(self.permission(cam), (True, False), "granted, and still the user's to change")
        info = self.agent.set_permission(self.token, self.DUMMY, cam, False)
        self.assertEqual(self.permission(cam), (False, False), "removed, and still the user's to change")
        self.agent.shift(self.token, [self.DUMMY])
        with self.assertRaises(ac.AgentError):
            self.agent.set_permission(self.token, self.DUMMY, cam, True)
        self.assertTrue(self.agent.app_info(self.DUMMY)["blocked"])
        with self.assertRaises(ac.AgentError):
            self.agent.set_permission("0" * 32, self.DUMMY, cam, True)
        self.agent.unshift(self.token)
        self.assertIn("Success", self.sh(f"pm uninstall {self.DUMMY}"))

    def test_18_release_and_uninstall(self):
        self.agent.shift(self.token, self.targets)
        self.agent.release(self.token)
        st = self.agent.status(self.token)
        self.assertFalse(st["owner"] or st["paired"] or st["shifted"])
        for p in self.targets:
            self.assertFree(p)
        self.agent.uninstall()
        self.assertFalse(self.agent.installed())

if __name__ == "__main__":
    unittest.main()
