import base64
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fakes import FakeAdb, FakePhone, ac, data_env, dumpsys_account
import platform_support as plat

TOKEN = "0123456789abcdef0123456789abcdef"

def agent_for(phone):
    return ac.Agent(FakeAdb(phone), "SERIAL1")

class DevicesTest(unittest.TestCase):
    def test_parses_states_and_models(self):
        adb = FakeAdb(devices=[("A1", "device", "Pixel_8_Pro"), ("B2", "unauthorized", ""), ("C3", "offline", "")])
        devs = adb.devices()
        self.assertEqual([(d.serial, d.state) for d in devs],
                         [("A1", "device"), ("B2", "unauthorized"), ("C3", "offline")])
        self.assertEqual(devs[0].model, "Pixel 8 Pro")

    def test_ignores_daemon_banner_and_blank_lines(self):
        adb = ac.Adb("/fake")
        out = ("* daemon not running; starting now at tcp:5037\n* daemon started successfully\n"
               "List of devices attached\nXYZ\tdevice usb:1-1 model:SM_S911B\n\n")
        with mock.patch.object(adb, "run", return_value=(0, out)):
            devs = adb.devices()

        self.assertEqual([(d.serial, d.model) for d in devs], [("XYZ", "SM S911B")])

    def test_no_devices(self):
        self.assertEqual(FakeAdb(devices=[]).devices(), [])

class RunTest(unittest.TestCase):
    def test_timeout_becomes_adb_error(self):
        adb = ac.Adb("/fake")
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("adb", 1)):
            with self.assertRaises(ac.AdbError):
                adb.run(["devices"])

    def test_passes_serial(self):
        adb = ac.Adb("/usr/bin/adb")
        done = subprocess.CompletedProcess([], 0, b"ok", b"")
        with mock.patch("subprocess.run", return_value=done) as run:
            self.assertEqual(adb.run(["shell", "id"], serial="S1"), (0, "ok"))
        self.assertEqual(run.call_args[0][0], ["/usr/bin/adb", "-s", "S1", "shell", "id"])

class FindAdbTest(unittest.TestCase):
    @unittest.skipIf(plat.WINDOWS, "Linux layout; test_platform covers Windows")
    def test_prefers_path_then_android_home(self):
        with tempfile.TemporaryDirectory() as d:
            tool = Path(d, "platform-tools", "adb")
            tool.parent.mkdir()
            tool.write_text("#!/bin/sh\n")
            tool.chmod(0o755)
            with mock.patch("shutil.which", return_value=None), \
                    mock.patch.dict(os.environ, {"ANDROID_HOME": d}, clear=False):
                self.assertEqual(ac.find_adb(), str(tool))
            with mock.patch("shutil.which", return_value="/usr/bin/adb"), \
                    mock.patch("os.access", return_value=True):
                self.assertEqual(ac.find_adb(), "/usr/bin/adb")

    def test_none_when_missing(self):
        with mock.patch("shutil.which", return_value=None), mock.patch("os.access", return_value=False):
            self.assertIsNone(ac.find_adb())

class CallTest(unittest.TestCase):
    def test_round_trip_through_provider_format(self):
        phone = FakePhone().ready(TOKEN)
        st = agent_for(phone).status(TOKEN)
        self.assertTrue(st["ok"] and st["owner"] and st["authorized"])
        self.assertEqual(st["model"], "Google Pixel 8")

    def test_payload_is_shell_safe_base64(self):
        adb = FakeAdb(FakePhone().ready(TOKEN))
        ac.Agent(adb, "S").shift(TOKEN, ["com.x.y", "weird'pkg; rm -rf /"])
        cmd = adb.log[-1][1]
        arg = cmd.split("--arg ")[1]
        self.assertRegex(arg, r"^[A-Za-z0-9+/=]+$")
        self.assertEqual(json.loads(base64.b64decode(arg))["packages"], ["com.x.y", "weird'pkg; rm -rf /"])

    def test_json_with_brackets_inside_strings(self):
        a = ac.Agent(ac.Adb("/fake"), "S")
        out = 'Result: Bundle[{json={"ok":true,"model":"Odd }] Phone","selected":[]}}]\n'
        with mock.patch.object(a, "shell", return_value=out):
            self.assertEqual(a.call("status")["model"], "Odd }] Phone")

    def test_agent_errors_carry_code(self):
        phone = FakePhone().ready(TOKEN)
        with self.assertRaises(ac.AgentError) as cm:
            agent_for(phone).unshift("f" * 32)
        self.assertEqual(cm.exception.code, "bad_key")

    def test_missing_agent_is_adb_error(self):
        with self.assertRaises(ac.AdbError) as cm:
            agent_for(FakePhone()).status(TOKEN)
        self.assertIn("isn't installed", str(cm.exception))

    def test_garbage_output_is_adb_error(self):
        a = ac.Agent(ac.Adb("/fake"), "S")
        with mock.patch.object(a, "shell", return_value="error: device offline"):
            with self.assertRaises(ac.AdbError) as cm:
                a.call("status")
        self.assertIn("device offline", str(cm.exception))

    def test_packages_are_sent_sorted(self):
        phone = FakePhone().ready(TOKEN)
        agent_for(phone).select(TOKEN, {"b.b", "a.a"})
        self.assertEqual(sorted(phone.selected), ["a.a", "b.b"])

class TimingCommandsTest(unittest.TestCase):
    NIGHT = {"id": "n1", "name": "Night", "enabled": True, "days": [1, 2, 3, 4, 5, 6, 7],
             "start": "22:30", "end": "07:00"}

    def sent(self, adb):
        cmd = adb.log[-1][1]
        return json.loads(base64.b64decode(cmd.split("--arg ")[1]))

    def test_plain_shift_has_no_minutes(self):
        adb = FakeAdb(FakePhone().ready(TOKEN))
        ac.Agent(adb, "S").shift(TOKEN, ["a.b"])
        self.assertNotIn("minutes", self.sent(adb))

    def test_timed_shift_sends_minutes(self):
        phone = FakePhone().ready(TOKEN)
        adb = FakeAdb(phone)
        st = ac.Agent(adb, "S").shift(TOKEN, ["com.instagram.android"], minutes=90)
        self.assertEqual(self.sent(adb)["minutes"], 90)
        self.assertEqual(st["mode"], "timer")
        self.assertAlmostEqual(st["ends"] - st["now"], 90 * 60_000, delta=2000)

    def test_timed_shift_out_of_range_is_refused(self):
        a = agent_for(FakePhone().ready(TOKEN))
        for minutes in (0, 8 * 24 * 60):
            with self.subTest(minutes=minutes), self.assertRaises(ac.AgentError) as cm:
                a.shift(TOKEN, ["a.b"], minutes=minutes)
            self.assertEqual(cm.exception.code, "bad_request")

    def test_schedules_round_trip(self):
        phone = FakePhone().ready(TOKEN)
        st = agent_for(phone).set_schedules(TOKEN, [self.NIGHT])
        self.assertEqual(st["schedules"], [self.NIGHT])

    def test_bad_schedules_are_refused(self):
        a = agent_for(FakePhone().ready(TOKEN))
        for bad in (dict(self.NIGHT, start="25:00"), dict(self.NIGHT, days=[0]), dict(self.NIGHT, days=[])):
            with self.subTest(bad=bad), self.assertRaises(ac.AgentError) as cm:
                a.set_schedules(TOKEN, [bad])
            self.assertEqual(cm.exception.code, "bad_request")

    def test_schedules_need_the_key(self):
        with self.assertRaises(ac.AgentError) as cm:
            agent_for(FakePhone().ready(TOKEN)).set_schedules("f" * 32, [])
        self.assertEqual(cm.exception.code, "bad_key")

    def test_status_tells_the_phone_which_edition_this_is(self):
        phone = FakePhone().ready(TOKEN)
        agent_for(phone).status(TOKEN)
        self.assertEqual(phone.edition, "free")

    def test_allow_background_runs_both_commands(self):
        adb = FakeAdb(FakePhone().ready(TOKEN))
        ac.Agent(adb, "S").allow_background()
        cmds = [c[1] for c in adb.log if c[0] == "shell"]
        self.assertIn("dumpsys deviceidle whitelist +app.anchor.agent", cmds)
        self.assertIn("cmd appops set app.anchor.agent SCHEDULE_EXACT_ALARM allow", cmds)
        self.assertIn("cmd appops set app.anchor.agent GET_USAGE_STATS allow", cmds)

    def test_schedule_hides_only_its_own_app(self):
        phone = FakePhone().ready(TOKEN)
        phone.selected = {"com.instagram.android"}
        a = agent_for(phone)
        a.set_schedules(TOKEN, [dict(self.NIGHT, packages=["com.google.android.youtube"])])
        phone.active_windows = {"n1": FakePhone.now() + 3_600_000}
        phone._apply()
        st = a.status(TOKEN)
        self.assertIsNone(st["mode"])
        self.assertFalse(st["shifted"])
        self.assertEqual(list(st["scheduled_now"]), ["com.google.android.youtube"])
        self.assertEqual(st["blocked"], ["com.google.android.youtube"])

    def test_unshift_during_schedule_pauses_it(self):
        phone = FakePhone().ready(TOKEN)
        phone.schedules = [dict(self.NIGHT, packages=["com.google.android.youtube"])]
        end = FakePhone.now() + 3_600_000
        phone.active_windows = {"n1": end}
        a = agent_for(phone)
        self.assertIn("com.google.android.youtube", a.status(TOKEN)["scheduled_now"])
        st = a.unshift(TOKEN)
        self.assertEqual(st["scheduled_now"], {})
        self.assertEqual(st["paused"], {"n1": end})

class InstallBlocksTest(unittest.TestCase):
    IG = {"pkg": "com.instagram.android", "name": "Instagram"}
    TT = {"pkg": "com.zhiliaoapp.musically", "name": "TikTok"}

    def test_round_trip_and_needs_key(self):
        phone = FakePhone().ready(TOKEN)
        st = agent_for(phone).set_install_blocks(TOKEN, [self.TT])
        self.assertEqual(st["install_blocks"], [self.TT])
        self.assertTrue(st["install_blocks_set"])
        with self.assertRaises(ac.AgentError) as cm:
            agent_for(phone).set_install_blocks("f" * 32, [])
        self.assertEqual(cm.exception.code, "bad_key")

    def test_bad_package_is_refused(self):
        with self.assertRaises(ac.AgentError) as cm:
            agent_for(FakePhone().ready(TOKEN)).set_install_blocks(TOKEN, [{"pkg": "not a package", "name": "x"}])
        self.assertEqual(cm.exception.code, "bad_request")

    def test_installed_apps_are_kept_and_new_installs_caught(self):
        phone = FakePhone().ready(TOKEN)
        a = agent_for(phone)
        st = a.set_install_blocks(TOKEN, [self.IG, self.TT])
        self.assertEqual(st["install_kept"], ["com.instagram.android"])
        self.assertEqual(st["install_caught"], [])
        self.assertNotIn("com.instagram.android", st["blocked"], "already installed: not affected")
        phone.install("com.zhiliaoapp.musically", "TikTok")
        st = a.status(TOKEN)
        self.assertEqual(st["install_caught"], ["com.zhiliaoapp.musically"])
        self.assertIn("com.zhiliaoapp.musically", st["blocked"])

        del phone.apps["com.instagram.android"]
        phone._apply()
        phone.install("com.instagram.android", "Instagram")
        self.assertIn("com.instagram.android", a.status(TOKEN)["install_caught"])

    def test_release_unblocks(self):
        phone = FakePhone().ready(TOKEN)
        a = agent_for(phone)
        a.set_install_blocks(TOKEN, [self.TT])
        phone.install("com.zhiliaoapp.musically", "TikTok")
        self.assertIn("com.zhiliaoapp.musically", phone.blocked)
        st = a.set_install_blocks(TOKEN, [])
        self.assertEqual(st["blocked"], [])

class AppsTest(unittest.TestCase):
    def test_reads_zip_and_sorts_by_label(self):
        phone = FakePhone(apps=[("z.z", "zebra"), ("a.a", "Apple"), ("m.m", "Mango")]).ready(TOKEN)
        apps, icons = agent_for(phone).apps()
        self.assertEqual([a["label"] for a in apps], ["Apple", "Mango", "zebra"])
        self.assertEqual(set(icons), {"z.z", "a.a", "m.m"})
        self.assertTrue(icons["a.a"].startswith(b"\x89PNG"))

    def test_non_zip_reply_is_adb_error(self):
        with self.assertRaises(ac.AdbError):
            agent_for(FakePhone()).apps()

class InstallTest(unittest.TestCase):
    def test_success(self):
        phone = FakePhone()
        agent_for(phone).install("x.apk")
        self.assertTrue(phone.installed)

    def test_failures_map_to_friendly_errors(self):
        cases = {
            "Failure [INSTALL_FAILED_USER_RESTRICTED: Install canceled by user]": "blocked the install",
            "Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package app.anchor.agent "
            "signatures do not match newer version; ignoring!]": "different Anchor",
            "adb: failed to install x.apk: Failure [INSTALL_FAILED_INSUFFICIENT_STORAGE]": "Couldn't install",
        }
        for output, title in cases.items():
            phone = FakePhone()
            phone.install_output = output
            with self.subTest(output=output), self.assertRaises(ac.SetupError) as cm:
                agent_for(phone).install("x.apk")
            self.assertIn(title, cm.exception.title)
            self.assertEqual(cm.exception.details, output)

class DeviceOwnerTest(unittest.TestCase):
    def test_success(self):
        phone = FakePhone()
        phone.installed = True
        agent_for(phone).set_device_owner()
        self.assertTrue(phone.owner)

    def test_already_owner_from_earlier_attempt_is_success(self):
        phone = FakePhone()
        phone.installed = True

        phone.dpm_output = (
            "app.anchor.agent/.AdminReceiver was already an admin for user 0. No need to set it again.\n\n"
            "Exception occurred while executing 'set-device-owner':\njava.lang.IllegalStateException: "
            "Trying to set the device owner (app.anchor.agent/.AdminReceiver), but device owner "
            "(app.anchor.agent/.AdminReceiver) is already set.")
        agent_for(phone).set_device_owner()

    def test_real_android_errors_map_to_guidance(self):

        cases = {
            "java.lang.IllegalStateException: Not allowed to set the device owner because there are "
            "already some accounts on the device": "Remove the accounts",
            "java.lang.IllegalStateException: Not allowed to set the device owner because there are "
            "already several users on the device": "extra users",
            "java.lang.IllegalStateException: Trying to set the device owner (app.anchor.agent/.AdminReceiver), "
            "but device owner (com.corp.mdm/.Admin) is already set.": "Another app already manages",
            "java.lang.SecurityException: Neither user 2000 nor current process has "
            "android.permission.MANAGE_DEVICE_ADMINS.": "developer switch",
            "Error: Unknown admin: ComponentInfo{app.anchor.agent/.AdminReceiver}": "Couldn't make Anchor",
        }
        for output, title in cases.items():
            phone = FakePhone()
            phone.installed = True
            phone.dpm_output = output
            with self.subTest(output=output[:60]), self.assertRaises(ac.SetupError) as cm:
                agent_for(phone).set_device_owner()
            self.assertIn(title, cm.exception.title)
            self.assertIn(output, cm.exception.details)

class AccountsTest(unittest.TestCase):
    MEETUP = ("me@example.com", "com.meetup.auth", "com.meetup")

    def phone_with(self, *accounts):
        phone = FakePhone(apps=[("com.meetup", "Meetup"), ("com.whatsapp", "WhatsApp")])
        phone.installed = True
        phone.accounts = list(accounts)
        return phone

    def test_parses_accounts_and_owning_apps(self):
        phone = self.phone_with(self.MEETUP, ("me@gmail.com", "com.google", "com.google.android.gms"))
        self.assertEqual(agent_for(phone).accounts(), [
            ac.Account("me@example.com", "com.meetup.auth", "com.meetup"),
            ac.Account("me@gmail.com", "com.google", "com.google.android.gms"),
        ])

    def test_ignores_history_and_lists_each_account_once(self):
        out = dumpsys_account([self.MEETUP]) + dumpsys_account([self.MEETUP])
        a = ac.Agent(ac.Adb("/fake"), "S")
        with mock.patch.object(a, "shell", return_value=out):
            self.assertEqual(len(a.accounts()), 1)
        with mock.patch.object(a, "shell", return_value=dumpsys_account([])):
            self.assertEqual(a.accounts(), [])

    def test_setup_error_names_the_accounts_left(self):
        phone = self.phone_with(self.MEETUP)
        with self.assertRaises(ac.SetupError) as cm:
            agent_for(phone).set_device_owner()
        body = cm.exception.body
        self.assertIn("This account is still on your phone", body)
        self.assertIn("Meetup: me@example.com", body)
        self.assertIn("Remove it in Settings", body)
        self.assertIn("some accounts on the device", cm.exception.details)

    def test_google_gets_a_friendly_name_and_plural_wording(self):
        phone = self.phone_with(self.MEETUP, ("me@gmail.com", "com.google", "com.google.android.gms"))
        with self.assertRaises(ac.SetupError) as cm:
            agent_for(phone).set_device_owner()
        self.assertIn("These 2 accounts are", cm.exception.body)
        self.assertIn("Google: me@gmail.com", cm.exception.body)
        self.assertIn("Remove them in Settings", cm.exception.body)

    def test_unknown_app_falls_back_to_package_name(self):
        phone = self.phone_with(("x", "org.example.sync", "org.example"))
        with self.assertRaises(ac.SetupError) as cm:
            agent_for(phone).set_device_owner()
        self.assertIn("org.example: x", cm.exception.body)

    def test_generic_advice_when_accounts_cant_be_listed(self):
        a = ac.Agent(ac.Adb("/fake"), "S")
        error = "java.lang.IllegalStateException: ... already some accounts on the device"
        with mock.patch.object(a, "shell", side_effect=[error, ac.AdbError("gone")]):
            with self.assertRaises(ac.SetupError) as cm:
                a.set_device_owner()
        self.assertIn("remove every account", cm.exception.body)

class KeyStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, data_env(self.tmp.name))
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_creates_key_once_and_keeps_it_private(self):
        ks = ac.KeyStore()
        t1 = ks.token
        self.assertRegex(t1, r"^[0-9a-f]{32}$")
        self.assertEqual(ac.KeyStore().token, t1)
        if not plat.WINDOWS:
            self.assertEqual(stat.S_IMODE(os.stat(ks.path).st_mode), 0o600)
        self.assertEqual(ks.path, Path(self.tmp.name, "anchor", "key.json"))

    def test_format_and_parse_round_trip(self):
        shown = ac.KeyStore.format(TOKEN)
        self.assertEqual(shown, "0123-4567-89AB-CDEF-0123-4567-89AB-CDEF")
        self.assertEqual(ac.KeyStore.parse(shown), TOKEN)
        self.assertEqual(ac.KeyStore.parse("  0123 4567 89ab cdef 0123 4567 89AB CDEF\n"), TOKEN)

    def test_parse_rejects_bad_keys(self):
        for bad in ("", "1234", TOKEN + "00", "ZZZZ" * 8):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ac.KeyStore.parse(bad)

    def test_keeps_one_phone_and_refuses_others(self):
        ks = ac.KeyStore()
        ks.claim({"device_id": "A", "model": "Phone A"})
        self.assertIsNone(ks.other_phone({"device_id": "A"}))
        self.assertEqual(ks.other_phone({"device_id": "B"})["model"], "Phone A")

    def test_using_a_backup_key_keeps_the_phone(self):
        ks = ac.KeyStore()
        ks.claim({"device_id": "A"})
        ks.set(TOKEN)
        self.assertEqual(ks.phone()["id"], "A")

    def test_freeing_the_slot_only_for_that_phone(self):
        ks = ac.KeyStore()
        ks.claim({"device_id": "A"})
        ks.free_slot("B")
        self.assertEqual(ks.phone()["id"], "A")
        ks.free_slot("A")
        self.assertIsNone(ks.phone())

    def test_forgetting_the_phone_changes_the_key(self):
        ks = ac.KeyStore()
        old = ks.token
        ks.claim({"device_id": "A"})
        ks.forget_phone()
        self.assertIsNone(ks.phone())
        self.assertNotEqual(ks.token, old)

    def test_key_copied_to_another_computer_has_no_phone(self):
        ks = ac.KeyStore()
        ks.claim({"device_id": "A"})
        with mock.patch.object(ac, "machine_id", return_value="another-computer"):
            self.assertIsNone(ks.phone())
            self.assertIsNone(ks.other_phone({"device_id": "B"}))

class FakePhoneContractTest(unittest.TestCase):

    def test_unpaired_phone_rejects_commands_and_pairs_once(self):
        phone = FakePhone()
        phone.installed = phone.owner = True
        a = agent_for(phone)
        with self.assertRaises(ac.AgentError):
            a.shift(TOKEN, ["com.instagram.android"])
        a.pair(TOKEN)
        with self.assertRaises(ac.AgentError) as cm:
            a.pair("f" * 32)
        self.assertEqual(cm.exception.code, "already_paired")

    def test_protected_apps_fail_and_unshift_clears(self):
        phone = FakePhone().ready(TOKEN)
        a = agent_for(phone)
        st = a.shift(TOKEN, ["com.instagram.android", "com.google.android.dialer"])
        self.assertEqual(st["blocked"], ["com.instagram.android"])
        self.assertEqual(st["failed"], ["com.google.android.dialer"])
        st = a.unshift(TOKEN)
        self.assertFalse(st["shifted"])
        self.assertEqual(st["blocked"], [])
        self.assertEqual(st["selected"], [], "releasing all empties the anchored list")

if __name__ == "__main__":
    unittest.main()
