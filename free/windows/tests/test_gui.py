"""Drives the real Anchor window (Qt) against a fake phone. Runs without a screen (offscreen Qt).

The same scenarios as the Linux app's tests (free/linux/tests/test_gui.py)."""

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fakes import FakeAdb, FakePhone, ac, data_env  # noqa: E402

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QPushButton  # noqa: E402

import anchor  # noqa: E402
import platform_support as plat  # noqa: E402
import widgets  # noqa: E402

REAL_ERROR_DIALOG = anchor.AnchorWindow.error_dialog

INSTAGRAM, YOUTUBE, DIALER = "com.instagram.android", "com.google.android.youtube", "com.google.android.dialer"
REDDIT = "com.reddit.frontpage"


def shown(widget):
    return not widget.isHidden()


class GuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = anchor.make_app(["anchor-tests"])
        # Making a placeholder signing key takes a moment; make one for the whole run.
        cls.key_tmp = tempfile.TemporaryDirectory()
        with mock.patch.dict(os.environ, data_env(cls.key_tmp.name)):
            import placeholder
            placeholder.ensure_key()
            cls.key_dir = placeholder.key_dir()

    @classmethod
    def tearDownClass(cls):
        cls.key_tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.errors, self.toasts, self.dialogs = [], [], []
        patches = [
            mock.patch.dict(os.environ, data_env(self.tmp.name)),
            mock.patch.object(plat.Path, "home", return_value=plat.Path(self.tmp.name)),  # never the real home
            mock.patch.object(anchor.ac, "find_adb", return_value="/fake/adb"),
            mock.patch.object(anchor.ac, "Adb", side_effect=lambda path: self.adb),
            # Tests trigger polls by hand instead of every 2 seconds.
            mock.patch.object(anchor.AnchorWindow, "start_polling", lambda win: None),
            mock.patch.object(anchor.AnchorWindow, "error_dialog",
                              lambda win, title, body, details="": self.errors.append((title, body))),
            mock.patch.object(anchor.AnchorWindow, "toast",
                              lambda win, text, timeout=3: self.toasts.append(text)),
            mock.patch.object(widgets.Overlay, "present", lambda d, parent=None: self.dialogs.append(d)),
            # The system password prompt: tests decide what the user does ("ok" unless set).
            mock.patch.object(anchor, "system_password_check", lambda: self.password_answer),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.token = ac.KeyStore().token
        shutil.copytree(self.key_dir, os.path.join(self.tmp.name, "anchor", "placeholder-key"))
        self.win = None
        self.password_answer = "ok"

    def tearDown(self):
        # Let this test's background work and its callbacks finish before the next test starts.
        self.pump(lambda: not anchor.RUNNING, timeout=20, fail=False)
        self.pump(lambda: False, timeout=0.1, fail=False)
        if self.win:
            self.win.close()
            self.win.deleteLater()
            self.pump(lambda: False, timeout=0.05, fail=False)

    # ---- helpers ----
    def open(self, phone=None, devices=None):
        self.phone = phone or FakePhone()
        self.adb = FakeAdb(self.phone, devices)
        self.win = anchor.AnchorWindow(self.app)
        self.win.show()
        return self.win

    def pump(self, cond, timeout=15.0, fail=True, what="condition"):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            QApplication.processEvents()
            if cond():
                return True
            time.sleep(0.01)
        if fail:
            self.fail(f"timed out waiting for {what}")
        return False

    def page(self):
        return self.win.page_name()

    def wait_page(self, name, timeout=15.0):
        self.pump(lambda: self.page() == name, timeout, what=f"page '{name}' (now '{self.page()}')")

    def ready_phone(self, **kw):
        return FakePhone(**kw).ready(self.token)

    def toggle(self, pkg, on=True):
        """Clicks the app's Anchor (on) or Release (off) button if it isn't in that state already."""
        if (pkg in self.win.selected) != on:
            self.win.rows[pkg].anchor_button.click()

    def wait_synced(self):
        self.pump(lambda: self.win.sync_source is None and not self.win.working, what="selection sync")

    # ---- connection states ----
    def test_no_phone_shows_connect_page(self):
        self.open(devices=[])
        self.wait_page("nophone")

    def test_unauthorized_phone_asks_to_allow(self):
        self.open(devices=[("S1", "unauthorized", "")])
        self.wait_page("unauthorized")

    def test_unplugging_returns_to_connect_page(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.adb.device_list = []
        self.win.poll()
        self.wait_page("nophone")

    def test_missing_adb_says_so(self):
        with mock.patch.object(anchor.ac, "find_adb", return_value=None):
            self.open()
        self.assertEqual(self.page(), "noadb")

    # ---- setup ----
    def test_fresh_phone_goes_through_setup(self):
        self.open(FakePhone())
        self.wait_page("setup")
        self.assertEqual(self.win.setup_button.text(), "Set up phone")
        self.win.setup_button.click()
        self.wait_page("main")
        self.assertTrue(self.phone.installed and self.phone.owner)
        self.assertEqual(self.phone.token_hash, FakePhone._hash(self.token))
        self.assertTrue(any("ready" in t for t in self.toasts), self.toasts)

    def test_setup_error_shows_guidance_and_can_retry(self):
        phone = FakePhone()
        phone.dpm_output = ("java.lang.IllegalStateException: Not allowed to set the device owner "
                            "because there are already some accounts on the device")
        self.open(phone)
        self.wait_page("setup")
        self.win.setup_button.click()
        self.pump(lambda: self.errors, what="error dialog")
        self.assertIn("Remove the accounts", self.errors[0][0])
        steps = [s.get_visible_child_name() for s in self.win.step_rows]
        self.assertEqual(steps, ["done", "todo", "todo"])
        self.assertTrue(self.win.setup_button.isEnabled())
        # The user removes the accounts and tries again.
        phone.dpm_output = None
        self.win.setup_button.click()
        self.wait_page("main")

    def test_accounts_error_names_the_apps(self):
        phone = FakePhone(apps=[("com.meetup", "Meetup")])
        phone.accounts = [("me@example.com", "com.meetup.auth", "com.meetup")]
        self.open(phone)
        self.wait_page("setup")
        self.win.setup_button.click()
        self.pump(lambda: self.errors, what="error dialog")
        title, body = self.errors[0]
        self.assertIn("Remove the accounts", title)
        self.assertIn("Meetup: me@example.com", body)

    def test_long_error_details_stay_inside_the_window(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        trace = "java.lang.IllegalStateException: " + "x" * 400 + "\n" + "\tat com.android.Foo(Foo.java:1)\n" * 80
        REAL_ERROR_DIALOG(self.win, "Title", "Body", trace)
        d = self.dialogs[-1]
        text = d.get_extra_child().findChild(QPlainTextEdit)
        self.assertFalse(shown(text), "folded away at first")
        d.get_extra_child().findChild(QPushButton).click()
        self.assertTrue(shown(text))
        self.assertLessEqual(text.maximumHeight(), 300, "details scroll instead of growing the dialog")
        self.assertLessEqual(d.panel_width, 440, "and the dialog keeps its width")

    def test_half_set_up_phone_offers_to_continue(self):
        phone = FakePhone()
        phone.installed = True
        self.open(phone)
        self.wait_page("setup")
        self.assertEqual(self.win.setup_button.text(), "Continue setup")
        self.assertEqual(self.win.step_rows[0].get_visible_child_name(), "done")

    def test_outdated_phone_app_is_upgraded(self):
        self.open(self.ready_phone(version=ac.AGENT_VERSION - 1))
        self.wait_page("main")
        self.assertIn("install", [cmd[0] for cmd in self.adb.log])
        self.assertEqual(self.phone.version, ac.AGENT_VERSION)

    # ---- pairing ----
    def test_phone_paired_with_other_computer(self):
        other = "f" * 32
        self.open(FakePhone().ready(other))
        self.wait_page("foreign")
        self.win.on_import()
        dialog = self.dialogs[-1]
        dialog.get_extra_child().setText(ac.KeyStore.format(other))
        dialog.emit("response", "use")
        self.wait_page("main")
        self.assertEqual(ac.KeyStore().token, other)

    def test_bad_backup_key_is_rejected(self):
        self.open(FakePhone().ready("f" * 32))
        self.wait_page("foreign")
        self.win.on_import()
        self.dialogs[-1].get_extra_child().setText("not a key")
        self.dialogs[-1].emit("response", "use")
        self.assertIn("doesn't look right", self.errors[0][0])
        self.assertEqual(ac.KeyStore().token, self.token)

    def test_backup_key_dialog_shows_formatted_key(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.on_backup()
        self.assertEqual(self.dialogs[-1].get_extra_child().text(), ac.KeyStore.format(self.token))

    def test_backup_key_can_be_copied(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.on_backup()
        self.dialogs[-1].emit("response", "copy")
        self.assertEqual(QApplication.clipboard().text(), ac.KeyStore.format(self.token))
        self.assertIn("Backup key copied", self.toasts)

    # ---- shifting ----
    def test_lists_phone_apps(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.assertEqual(set(self.win.rows), {p for p, _ in FakePhone().apps.items()})
        self.assertEqual(self.win.subtitle_label.text(), "Google Pixel 8")

    def open_shifted(self, *pkgs):
        phone = self.ready_phone()
        phone.selected, phone.shifted = set(pkgs), True
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        return phone

    def section_of(self, pkg):
        row = self.win.rows[pkg]
        if row in self.win.picked_section.rows:
            return "picked"
        if row in self.win.other_section.rows:
            return "other"
        return None

    def test_nothing_anchored_at_first(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.assertEqual(self.win.hero_title.text(), "Not anchored")
        self.assertEqual(self.win.hero_title.text(), "Not anchored")
        self.assertFalse(shown(self.win.hero_button), "nothing to release")
        self.assertEqual({r.anchor_button.text() for r in self.win.rows.values()}, {"Anchor"})
        self.assertFalse(shown(self.win.picked_section), "no empty Anchored section")
        self.assertEqual(self.win.other_section.title_label.text(), f"Your apps ({len(self.win.rows)})")

    def test_anchor_one_app_hides_it_right_away(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.toggle(INSTAGRAM)
        self.assertEqual(self.win.rows[INSTAGRAM].get_subtitle(), "Hiding…")
        self.wait_synced()
        self.assertEqual((self.phone.mode(), self.phone.blocked), ("manual", {INSTAGRAM}))
        row = self.win.rows[INSTAGRAM]
        self.assertEqual((row.anchor_button.text(), row.get_subtitle()), ("Release", "Hidden"))
        self.pump(lambda: self.section_of(INSTAGRAM) == "picked", what="row move")
        self.assertEqual(self.win.picked_section.title_label.text(), "Anchored apps (1)")
        self.assertEqual(self.win.hero_title.text(), "Anchored")
        self.assertEqual(self.win.hero_button.text(), "Release all")
        self.assertTrue(self.win.hero.property("anchored"), "the logo lights up while anchored")
        self.assertEqual(self.toasts[-1], "Instagram anchored: hidden from your phone")

    def test_release_one_app(self):
        phone = self.open_shifted(INSTAGRAM, YOUTUBE)
        self.assertEqual(self.win.rows[YOUTUBE].anchor_button.text(), "Release")
        self.toggle(YOUTUBE, False)
        self.assertEqual(self.win.rows[YOUTUBE].get_subtitle(), "Bringing back…")
        self.wait_synced()
        self.assertEqual((phone.mode(), phone.blocked), ("manual", {INSTAGRAM}))
        self.pump(lambda: self.section_of(YOUTUBE) == "other", what="row move")
        self.assertEqual(self.win.rows[YOUTUBE].anchor_button.text(), "Anchor")
        self.assertEqual(self.toasts[-1], "YouTube released: back on your phone")

    def test_releasing_the_last_app_stops_anchoring_but_not_schedules(self):
        phone = self.ready_phone()
        phone.selected, phone.shifted = {INSTAGRAM}, True
        phone.schedules = [dict(self.NIGHT)]
        phone.active_windows = {"n1": FakePhone.now() + 3_600_000}
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        self.toggle(INSTAGRAM, False)
        self.wait_synced()
        self.assertIsNone(phone.mode())
        self.assertEqual(phone.blocked, {YOUTUBE}, "YouTube's schedule keeps running")
        self.assertEqual(phone.paused, {})
        self.assertEqual(self.win.hero_title.text(), "On schedule")

    def test_release_all(self):
        phone = self.open_shifted(INSTAGRAM, YOUTUBE)
        self.win.hero_button.click()
        self.pump(lambda: phone.mode() is None and not self.win.working, what="release all")
        self.assertEqual((phone.blocked, phone.selected), (set(), set()))
        self.assertEqual(self.toasts[-1], "Released · all apps are back")
        self.assertEqual(self.win.hero_title.text(), "Not anchored")
        self.assertEqual(self.win.rows[INSTAGRAM].anchor_button.text(), "Anchor")

    def test_release_all_asks_for_the_password_first(self):
        phone = self.open_shifted(INSTAGRAM, YOUTUBE)
        for answer, message in (("cancelled", "Release all cancelled"), ("denied", "Password not accepted")):
            self.password_answer = answer
            self.win.hero_button.click()
            self.pump(lambda: any(message in t for t in self.toasts), what=answer)
            self.assertEqual(phone.blocked, {INSTAGRAM, YOUTUBE}, f"{answer}: still anchored")
            self.assertTrue(self.win.hero_button.isEnabled())
        self.password_answer = "ok"
        self.win.hero_button.click()
        self.pump(lambda: phone.mode() is None and not self.win.working, what="release after password")
        self.assertEqual(phone.blocked, set())

    def test_release_all_without_a_password_prompt(self):
        phone = self.open_shifted(INSTAGRAM)
        self.password_answer = "missing"
        self.win.hero_button.click()
        self.pump(lambda: self.errors, what="error")
        self.assertIn("Can't ask for your password", self.errors[0][0])
        self.assertEqual(phone.blocked, {INSTAGRAM})

    def test_single_release_needs_no_password(self):
        phone = self.open_shifted(INSTAGRAM, YOUTUBE)
        self.password_answer = "denied"
        self.toggle(YOUTUBE, False)
        self.wait_synced()
        self.assertEqual(phone.blocked, {INSTAGRAM})

    def test_several_quick_clicks_are_sent_together(self):
        phone = self.open_shifted(INSTAGRAM)
        self.toggle(YOUTUBE)
        self.toggle(REDDIT)
        self.wait_synced()
        self.assertEqual(phone.blocked, {INSTAGRAM, YOUTUBE, REDDIT})
        self.assertEqual(self.toasts[-1], "2 apps anchored: hidden from your phone")

    def test_protected_app_is_marked(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.toggle(DIALER)
        self.wait_synced()
        self.assertIn("protected", self.win.rows[DIALER].get_subtitle())
        self.pump(lambda: self.section_of(DIALER) == "picked", what="row move")
        self.assertEqual(self.toasts[-1], "Phone can't be hidden (protected by Android)")

    def test_anchor_started_on_phone_is_picked_up(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        phone.selected, phone.shifted = {INSTAGRAM}, True  # the user pressed "Anchor" on the phone
        phone._apply()
        self.win.poll()
        self.pump(lambda: self.win.hero_title.text() == "Anchored", what="status refresh")
        self.assertEqual(self.win.rows[INSTAGRAM].anchor_button.text(), "Release")

    def test_old_list_from_before_buttons_is_cleared(self):
        phone = self.ready_phone()
        phone.selected = {INSTAGRAM}  # saved, but not anchored
        self.open(phone)
        self.wait_page("main")
        self.assertEqual(phone.selected, set())
        self.assertEqual(self.win.rows[INSTAGRAM].anchor_button.text(), "Anchor")

    def test_phone_unplugged_while_anchoring_shows_error(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        with mock.patch.object(ac.Agent, "shift", side_effect=ac.AdbError("device not found")):
            self.toggle(INSTAGRAM)
            self.pump(lambda: any("Couldn't reach the phone" in t for t in self.toasts), what="error")
        self.pump(lambda: self.win.rows[INSTAGRAM].anchor_button.text() == "Anchor", what="undone")

    # ---- auto-release ----
    def test_timer_running_out_releases_the_apps(self):
        phone = self.ready_phone()
        phone.selected, phone.until = {INSTAGRAM}, FakePhone.now() + 600
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        self.assertEqual(self.win.rows[INSTAGRAM].anchor_button.text(), "Release")
        time.sleep(0.7)
        self.win.poll()
        self.pump(lambda: self.win.hero_title.text() == "Not anchored", what="timer end")
        self.assertEqual(self.win.rows[INSTAGRAM].anchor_button.text(), "Anchor")

    def test_release_all_ends_a_timer_early(self):
        phone = self.ready_phone()
        phone.selected, phone.until = {INSTAGRAM}, FakePhone.now() + 3_600_000
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        self.win.hero_button.click()
        self.pump(lambda: phone.mode() is None and not self.win.working, what="release")
        self.assertEqual(phone.blocked, set())

    # ---- uninstall ----
    def test_uninstall_button_only_on_apps_that_can_be_uninstalled(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.assertIsNone(self.win.rows[YOUTUBE].uninstall_button, "preinstalled system app")
        self.assertIsNotNone(self.win.rows[INSTAGRAM].uninstall_button)

    def test_buttons_line_up_in_columns(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.pump(lambda: False, timeout=0.2, fail=False)
        xs = {r.anchor_button.mapTo(self.win, r.anchor_button.rect().topLeft()).x() for r in self.win.rows.values()}
        self.assertEqual(len(xs), 1, "every Anchor button starts at the same x")

    def test_uninstall_an_app(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        self.win.rows[INSTAGRAM].uninstall_button.click()
        self.assertIn("Uninstall Instagram?", self.dialogs[-1].get_heading())
        self.dialogs[-1].emit("response", "uninstall")
        self.pump(lambda: INSTAGRAM not in self.win.rows, what="uninstall")
        self.assertNotIn(INSTAGRAM, phone.apps)
        self.assertIn("Instagram uninstalled", self.toasts)
        self.assertEqual(self.win.other_section.title_label.text(), f"Your apps ({len(self.win.rows)})",
                         "count updated")

    def test_never_allowing_an_app_on_the_phone_asks_then_uninstalls_it(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        self.win.add_install_blocks([{"pkg": INSTAGRAM, "name": "Instagram"}])
        self.assertEqual(self.dialogs[-1].get_heading(), "Uninstall Instagram?")
        self.dialogs[-1].emit("response", "uninstall")
        self.pump(lambda: INSTAGRAM in phone.placeholders and not self.win.placing, what="uninstall, then placeholder")
        self.assertNotIn(INSTAGRAM, phone.apps)
        self.assertIn(INSTAGRAM, {a["pkg"] for a in phone.install_blocks})
        self.assertNotIn(INSTAGRAM, phone.kept, "it was uninstalled first, so it isn't left alone")
        self.assertIn("Instagram uninstalled and added to Never allow", self.toasts)
        self.assertFalse(phone.install(INSTAGRAM, "Instagram"))

    def test_never_allowing_an_app_on_the_phone_can_be_cancelled(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        self.win.add_install_blocks([{"pkg": INSTAGRAM, "name": "Instagram"}])
        self.dialogs[-1].emit("response", "cancel")
        self.pump(lambda: False, timeout=0.3, fail=False)
        self.assertIn(INSTAGRAM, phone.apps)
        self.assertEqual(phone.install_blocks, [], "nothing is added")

    def test_never_allowing_an_anchored_or_system_app_doesnt_uninstall_it(self):
        phone = self.ready_phone()
        phone.selected, phone.shifted = {INSTAGRAM}, True
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        before = len(self.dialogs)
        self.win.add_install_blocks([{"pkg": INSTAGRAM, "name": "Instagram"}, {"pkg": YOUTUBE, "name": "YouTube"}])
        self.pump(lambda: len(phone.install_blocks) == 2, what="added")
        self.assertEqual(len(self.dialogs), before, "no question")
        self.assertIn(INSTAGRAM, phone.apps)
        self.assertIn(YOUTUBE, phone.apps)

    def test_details_have_uninstall_at_the_bottom(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        self.win.open_app_details({"pkg": YOUTUBE, "label": "YouTube"})
        self.assertIsNone(self.win.details.uninstall, "not for apps that came with the phone")
        self.win.open_app_details({"pkg": INSTAGRAM, "label": "Instagram"})
        self.win.details.uninstall.click()
        self.assertEqual(self.dialogs[-1].get_heading(), "Uninstall Instagram?")
        self.dialogs[-1].emit("response", "uninstall")
        self.pump(lambda: INSTAGRAM not in self.win.rows, what="uninstall")
        self.assertNotIn(INSTAGRAM, phone.apps)

    def test_details_show_a_spinner_until_they_load(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.open_app_details({"pkg": INSTAGRAM, "label": "Instagram"})
        d = self.win.details
        self.assertTrue(not d.loading.isHidden(), "a spinner first")
        self.assertFalse(not d.about.isHidden(), "no half-empty cards meanwhile")
        self.pump(lambda: d.page_widgets, what="details")
        self.assertFalse(not d.loading.isHidden())
        self.assertTrue(not d.about.isHidden() and not d.perms.isHidden() and not d.uninstall.isHidden(),
                        "then everything at once")

    def test_uninstall_needs_confirmation_in_the_list(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        self.win.rows[INSTAGRAM].uninstall_button.click()
        self.dialogs[-1].emit("response", "cancel")
        self.pump(lambda: False, timeout=0.3, fail=False)
        self.assertIn(INSTAGRAM, phone.apps)

    def test_uninstalling_a_never_allowed_app_puts_the_placeholder_in(self):
        phone = self.ready_phone()
        phone.install_blocks = [{"pkg": INSTAGRAM, "name": "Instagram"}]
        phone.kept = {INSTAGRAM}  # it was on the phone before it was added
        self.open(phone)
        self.wait_page("main")
        self.win.rows[INSTAGRAM].uninstall_button.click()
        self.dialogs[-1].emit("response", "uninstall")
        self.pump(lambda: INSTAGRAM in phone.placeholders and not self.win.placing, what="placeholder")
        self.assertFalse(phone.install(INSTAGRAM, "Instagram"))

    # ---- per-app schedules ----
    NIGHT = {"id": "n1", "name": "YouTube", "enabled": True, "days": [1, 2, 3, 4, 5, 6, 7],
             "start": "22:30", "end": "07:00", "packages": [YOUTUBE]}

    def window_rows(self):
        return list(self.win.app_dialog[2].card.rows)

    def add_window(self, pkg, days=None, start=(22, 30), end=(7, 0)):
        self.win.edit_window(pkg, None)
        d = self.dialogs[-1]
        if days is not None:
            for i, b in enumerate(d.day_buttons, start=1):
                b.setChecked(i in days)
        d.start_picker.set_minutes(start[0] * 60 + start[1])
        d.end_picker.set_minutes(end[0] * 60 + end[1])
        d.emit("response", "save")

    def is_accent(self, row):
        return row.sched_button.property("kind") == "icon-accent"

    def test_every_app_has_a_schedule_button(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        for pkg, row in self.win.rows.items():
            self.assertIn(row.label, row.sched_button.toolTip())
        self.assertTrue(self.phone.background_allowed, "phone is allowed to wake up on time")

    def test_open_app_schedule_starts_empty(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.rows[YOUTUBE].sched_button.click()
        self.assertEqual(self.dialogs[-1].get_heading(), "YouTube schedule")
        self.assertEqual([r.get_title() for r in self.window_rows()], ["Add a time"])

    def test_time_picker_wraps_around(self):
        picker = anchor.TimePicker(23 * 60 + 59)
        picker.step(0, 1, 23)
        picker.step(1, 1, 59)
        self.assertEqual(picker.minutes(), 0)
        self.assertEqual([lbl.text() for lbl in picker.labels], ["00", "00"])

    def test_add_a_time_to_one_app(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.open_app_schedule(YOUTUBE)
        self.add_window(YOUTUBE, start=(22, 30), end=(7, 0))
        self.pump(lambda: self.phone.schedules and not self.win.working, what="save")
        sch = self.phone.schedules[0]
        self.assertEqual((sch["packages"], sch["days"], sch["start"], sch["end"], sch["enabled"]),
                         ([YOUTUBE], [1, 2, 3, 4, 5, 6, 7], "22:30", "07:00", True))
        self.assertEqual(self.toasts[-1], "YouTube: Every day 22:30–07:00 saved")
        # The open dialog and the app's row both show it; other apps are untouched.
        self.assertEqual([r.get_title() for r in self.window_rows()], ["Every day", "Add a time"])
        self.assertEqual(self.win.rows[YOUTUBE].get_subtitle(), "Every day · 22:30–07:00")
        self.assertTrue(self.is_accent(self.win.rows[YOUTUBE]))
        self.assertEqual(self.win.rows[INSTAGRAM].get_subtitle(), INSTAGRAM)
        self.assertFalse(self.is_accent(self.win.rows[INSTAGRAM]))

    def test_each_app_keeps_its_own_times(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.add_window(YOUTUBE, start=(22, 30), end=(7, 0))
        self.pump(lambda: len(self.phone.schedules) == 1 and not self.win.working, what="save 1")
        self.add_window(INSTAGRAM, days=[1, 2, 3, 4, 5], start=(9, 0), end=(17, 0))
        self.pump(lambda: len(self.phone.schedules) == 2 and not self.win.working, what="save 2")
        self.add_window(YOUTUBE, days=[6, 7], start=(0, 0), end=(0, 0))
        self.pump(lambda: len(self.phone.schedules) == 3 and not self.win.working, what="save 3")
        by_app = {}
        for sch in self.phone.schedules:
            by_app.setdefault(sch["packages"][0], []).append((sch["days"], sch["start"], sch["end"]))
        self.assertEqual(by_app[INSTAGRAM], [([1, 2, 3, 4, 5], "09:00", "17:00")])
        self.assertEqual(by_app[YOUTUBE], [([1, 2, 3, 4, 5, 6, 7], "22:30", "07:00"), ([6, 7], "00:00", "00:00")])
        self.assertEqual(self.win.rows[INSTAGRAM].get_subtitle(), "Weekdays · 09:00–17:00")
        self.assertEqual(self.win.rows[YOUTUBE].get_subtitle(), "2 schedules")

    def test_edit_a_time(self):
        phone = self.ready_phone()
        phone.schedules = [dict(self.NIGHT)]
        self.open(phone)
        self.wait_page("main")
        self.win.open_app_schedule(YOUTUBE)
        self.window_rows()[0].activated.emit()
        d = self.dialogs[-1]
        d.end_picker.set_minutes(8 * 60)
        d.emit("response", "save")
        self.pump(lambda: phone.schedules[0]["end"] == "08:00" and not self.win.working, what="edit")
        self.assertEqual(len(phone.schedules), 1)

    def test_delete_a_time(self):
        phone = self.ready_phone()
        phone.schedules = [dict(self.NIGHT)]
        self.open(phone)
        self.wait_page("main")
        self.win.open_app_schedule(YOUTUBE)
        self.window_rows()[0].delete.click()
        self.pump(lambda: not phone.schedules and not self.win.working, what="delete")
        self.assertEqual([r.get_title() for r in self.window_rows()], ["Add a time"])
        self.assertEqual(self.win.rows[YOUTUBE].get_subtitle(), YOUTUBE)

    def test_switch_a_time_off(self):
        phone = self.ready_phone()
        phone.schedules = [dict(self.NIGHT)]
        self.open(phone)
        self.wait_page("main")
        self.win.open_app_schedule(YOUTUBE)
        self.window_rows()[0].switch.setChecked(False)
        self.pump(lambda: not phone.schedules[0]["enabled"] and not self.win.working, what="switch off")
        self.assertEqual(self.win.rows[YOUTUBE].get_subtitle(), "Every day · 22:30–07:00 · Off")
        self.assertFalse(self.is_accent(self.win.rows[YOUTUBE]))
        self.assertEqual(self.toasts[-1], "YouTube: Every day 22:30–07:00 turned off")

    def test_a_time_needs_a_day(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.add_window(YOUTUBE, days=[])
        self.assertIn("at least one day", self.errors[0][0])
        self.assertEqual(self.phone.schedules, [])

    def test_app_on_its_schedule_right_now(self):
        phone = self.ready_phone()
        phone.selected = {INSTAGRAM}
        phone.schedules = [dict(self.NIGHT)]
        phone.active_windows = {"n1": FakePhone.now() + 2 * 3_600_000}
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        # Only YouTube is hidden: Instagram is merely selected, and nothing is shifted.
        self.assertEqual(phone.blocked, {YOUTUBE})
        self.assertEqual(self.win.hero_title.text(), "On schedule")
        self.assertIn("YouTube is hidden by its schedule right now", self.win.hero_subtitle.text())
        self.assertTrue(self.win.rows[YOUTUBE].get_subtitle().startswith("Hidden by its schedule until "))
        self.assertTrue(shown(self.win.pause_button))
        self.assertFalse(shown(self.win.hero_button), "nothing anchored by hand")
        self.win.open_app_schedule(YOUTUBE)
        self.assertTrue(self.window_rows()[0].get_title().startswith("Hidden right now, until "))

    def test_bring_scheduled_apps_back_pauses_them(self):
        phone = self.ready_phone()
        phone.schedules = [dict(self.NIGHT)]
        end = FakePhone.now() + 2 * 3_600_000
        phone.active_windows = {"n1": end}
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        self.win.pause_button.click()
        self.pump(lambda: not phone.blocked and not self.win.working, what="pause")
        self.assertEqual(phone.paused, {"n1": end})
        self.assertIn("Scheduled apps are back · schedules paused until", self.toasts[-1])
        self.assertIn("Paused until", self.win.rows[YOUTUBE].get_subtitle())
        self.assertFalse(shown(self.win.pause_button))
        self.assertEqual(self.win.hero_title.text(), "Not anchored")

    def test_shift_and_schedule_together(self):
        phone = self.ready_phone()
        phone.schedules = [dict(self.NIGHT)]
        phone.active_windows = {"n1": FakePhone.now() + 3_600_000}
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        self.toggle(INSTAGRAM)
        self.wait_synced()
        self.assertEqual(phone.mode(), "manual")
        self.assertEqual(phone.blocked, {INSTAGRAM, YOUTUBE})
        self.assertIn("Release all also pauses that", self.win.hero_subtitle.text())
        self.win.hero_button.click()
        self.pump(lambda: phone.mode() is None and not self.win.working, what="unshift")
        self.assertEqual(phone.blocked, set())
        self.assertIn("n1", phone.paused)

    def test_old_general_schedules_are_removed(self):
        phone = self.ready_phone()
        phone.schedules = [{"id": "old", "name": "Night", "enabled": True, "days": [1], "start": "22:00",
                            "end": "06:00"}, dict(self.NIGHT)]
        self.open(phone)
        self.wait_page("main")
        self.pump(lambda: len(phone.schedules) == 1 and not self.win.working, what="cleanup")
        self.assertEqual(phone.schedules[0]["id"], "n1")
        self.assertIn("Old schedules were removed", self.toasts[-1])

    # ---- permissions ----
    def test_anchoring_removes_permissions_and_releasing_restores_them(self):
        phone = self.ready_phone()
        phone.granted = {INSTAGRAM: {"android.permission.CAMERA", "android.permission.ACCESS_FINE_LOCATION"},
                         YOUTUBE: {"android.permission.POST_NOTIFICATIONS"}}
        self.open(phone)
        self.wait_page("main")
        self.toggle(INSTAGRAM)
        self.wait_synced()
        self.assertEqual(phone.mode(), "manual")
        self.assertEqual(phone.granted.get(INSTAGRAM, set()), set(), "no permissions while anchored")
        self.assertEqual(self.win.rows[INSTAGRAM].get_subtitle(), "Hidden · 2 permissions removed")
        self.assertEqual(phone.granted[YOUTUBE], {"android.permission.POST_NOTIFICATIONS"}, "other apps untouched")
        self.toggle(INSTAGRAM, False)
        self.wait_synced()
        self.assertIsNone(phone.mode())
        self.assertEqual(phone.granted[INSTAGRAM], {"android.permission.CAMERA", "android.permission.ACCESS_FINE_LOCATION"})
        self.assertEqual(self.win.rows[INSTAGRAM].get_subtitle(), INSTAGRAM)

    def test_scheduled_app_loses_permissions_too(self):
        phone = self.ready_phone()
        phone.granted = {YOUTUBE: {"android.permission.POST_NOTIFICATIONS"}}
        phone.schedules = [dict(self.NIGHT)]
        phone.active_windows = {"n1": FakePhone.now() + 3_600_000}
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        self.assertIn("· 1 permission removed", self.win.rows[YOUTUBE].get_subtitle())
        self.assertEqual(phone.granted.get(YOUTUBE, set()), set())

    @unittest.skipIf(plat.WINDOWS, "polkit is Linux only")
    def test_password_check_reads_pkexec_answers(self):
        real = plat._polkit_password_check

        def done(code):
            return subprocess.CompletedProcess([], code)

        with mock.patch.object(plat.shutil, "which", return_value="/usr/bin/pkexec"):
            for code, answer in ((0, "ok"), (126, "cancelled"), (127, "denied"), (1, "denied")):
                with mock.patch.object(plat.subprocess, "run", return_value=done(code)) as run:
                    self.assertEqual(real(), answer, code)
                self.assertEqual(run.call_args[0][0][0], "pkexec", "the system's own prompt")
            for installed, command in ((True, plat.RELEASE_CHECK), (False, "/bin/true")):
                with mock.patch.object(plat.os, "access", return_value=installed), \
                        mock.patch.object(plat.subprocess, "run", return_value=done(0)) as run:
                    real()
                self.assertEqual(run.call_args[0][0][-1], command, "worded prompt only when its policy is installed")
        with mock.patch.object(plat.shutil, "which", return_value=None):
            self.assertEqual(real(), "missing")

    # ---- app details ----
    def open_details(self, pkg):
        self.win.rows[pkg].activated.emit()
        d = self.dialogs[-1]
        self.pump(lambda: d.perm_rows or d.perm_empty, what="details")
        return d

    def test_clicking_an_app_opens_details_and_doesnt_anchor(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        d = self.open_details(INSTAGRAM)
        self.assertEqual(d.get_title(), "Instagram")
        about = {r.get_title(): r.get_subtitle() for r in d.page_widgets}
        self.assertEqual(about["Version"], "1.2.3")
        self.assertEqual(about["Status"], "Not anchored")
        self.assertEqual(about["Type"], "Installed by you")
        self.assertEqual(phone.blocked, set(), "clicking the row doesn't anchor")
        self.assertEqual(self.win.rows[INSTAGRAM].anchor_button.text(), "Anchor")
        self.assertEqual(sorted(r.get_title() for r in d.perm_rows.values()), ["Camera", "Microphone", "Notifications"])
        self.assertEqual(d.perm_rows["android.permission.CAMERA"].get_subtitle(), "Take pictures and videos")

    def test_a_real_click_on_the_row_opens_details(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        row = self.win.rows[INSTAGRAM]
        QTest.mouseClick(row, Qt.LeftButton, pos=row.title_label.geometry().center())
        self.assertTrue(any(isinstance(d, widgets.PanelDialog) for d in self.dialogs))

    def test_grant_and_remove_a_permission(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        d = self.open_details(INSTAGRAM)
        d.perm_rows["android.permission.CAMERA"].set_active(True)
        self.pump(lambda: "android.permission.CAMERA" in phone.granted.get(INSTAGRAM, set()), what="grant")
        self.pump(lambda: d.perm_rows["android.permission.CAMERA"].isEnabled(), what="row refreshed")
        self.assertIn("Camera: allowed for Instagram", self.toasts)
        d.perm_rows["android.permission.CAMERA"].set_active(False)
        self.pump(lambda: "android.permission.CAMERA" not in phone.granted.get(INSTAGRAM, set()), what="remove")
        self.pump(lambda: any("removed for Instagram" in t for t in self.toasts), what="toast")

    def test_blocked_app_permissions_are_locked(self):
        phone = self.ready_phone()
        phone.granted = {INSTAGRAM: {"android.permission.CAMERA"}}
        phone.selected, phone.shifted = {INSTAGRAM}, True
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        d = self.open_details(INSTAGRAM)
        self.assertTrue(all(not r.isEnabled() for r in d.perm_rows.values()), "greyed out while anchored")
        self.assertIn("comes back when released", d.perm_rows["android.permission.CAMERA"].get_subtitle())
        self.assertIn("removed while Instagram is blocked", d.perms.description.text())
        self.assertEqual({r.get_title(): r.get_subtitle() for r in d.page_widgets}["Status"],
                         "Anchored: hidden from your phone")

    def test_app_without_permissions(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        d = self.open_details(REDDIT)
        self.assertEqual(d.perm_empty.get_title(), "No permissions to manage")

    def test_buttons_still_work_next_to_a_clickable_row(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        self.toggle(INSTAGRAM)
        self.wait_synced()
        self.assertEqual(phone.blocked, {INSTAGRAM})
        self.assertEqual([d for d in self.dialogs if isinstance(d, widgets.PanelDialog)], [])

    # ---- Never allow ----
    def never_rows(self):
        return {row.pkg: row for row in self.win.never_children if hasattr(row, "pkg")}

    def test_social_media_blocked_by_default_on_first_connect(self):
        phone = self.ready_phone()
        phone.install_blocks_set = False
        self.open(phone)
        self.wait_page("main")
        self.pump(lambda: phone.install_blocks and phone.placeholders and not self.win.placing, what="defaults")
        pkgs = {a["pkg"] for a in phone.install_blocks}
        self.assertIn("com.zhiliaoapp.musically", pkgs)
        self.assertNotIn("com.facebook.orca", pkgs, "Messenger stays allowed")
        self.assertIn("Social media apps are now on your 'Never allow' list", self.toasts)
        # Every default app that isn't on the phone gets a placeholder, so it can't be installed.
        self.assertEqual(phone.placeholders, pkgs - set(phone.apps))
        self.assertFalse(phone.install("com.zhiliaoapp.musically", "TikTok"), "Android refuses the install")
        self.pump(lambda: self.never_rows()["com.zhiliaoapp.musically"].get_subtitle() == "com.zhiliaoapp.musically",
                  what="row update")
        rows = self.never_rows()
        # Already on the phone: left alone. Not on the phone: can't be installed.
        self.assertIn("already on your phone", rows[INSTAGRAM].get_subtitle())
        self.assertNotIn(INSTAGRAM, phone.blocked)
        self.assertEqual(self.win.never_section.hint_label.text(), "Apps that can't be installed.")
        self.assertEqual(self.win.never_section.title_label.text(), f"Never allow ({len(pkgs)})")

    def test_never_allow_starts_folded(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.assertFalse(self.win.never_section.is_open)

    def test_defaults_are_not_re_added(self):
        phone = self.ready_phone()  # list already set (here: empty, the user released everything)
        self.open(phone)
        self.wait_page("main")
        self.pump(lambda: False, timeout=0.3, fail=False)
        self.assertEqual(phone.install_blocks, [])

    def test_never_allowed_app_cant_be_installed(self):
        phone = self.ready_phone()
        phone.install_blocks = [{"pkg": "com.zhiliaoapp.musically", "name": "TikTok"}]
        self.open(phone)
        self.wait_page("main")
        self.pump(lambda: "com.zhiliaoapp.musically" in phone.placeholders and not self.win.placing,
                  what="placeholder")
        self.assertFalse(phone.install("com.zhiliaoapp.musically", "TikTok"))
        self.assertEqual(self.never_rows()["com.zhiliaoapp.musically"].get_subtitle(), "com.zhiliaoapp.musically")
        self.assertEqual(phone.blocked, set(), "placeholders aren't counted as hidden apps")
        self.assertIn("1 app can't be installed on your phone now", self.toasts[-1])

    def test_fallback_when_the_phone_refuses_placeholders(self):
        phone = self.ready_phone()
        phone.refuse_placeholders = True
        phone.install_blocks = [{"pkg": "com.zhiliaoapp.musically", "name": "TikTok"}]
        self.open(phone)
        self.wait_page("main")
        self.pump(lambda: "com.zhiliaoapp.musically" in self.win.placeholder_failed, what="placeholder attempt")
        self.pump(lambda: "hidden right away" in self.never_rows()["com.zhiliaoapp.musically"].get_subtitle(),
                  what="fallback note")
        self.assertTrue(phone.install("com.zhiliaoapp.musically", "TikTok"))
        self.assertIn("com.zhiliaoapp.musically", phone.blocked, "it's hidden the moment it's installed")
        self.win.poll()
        self.pump(lambda: self.never_rows()["com.zhiliaoapp.musically"].uninstall is not None, what="caught row")

    def test_uninstall_a_blocked_app_that_got_installed(self):
        phone = self.ready_phone()
        phone.install_blocks = [{"pkg": "com.zhiliaoapp.musically", "name": "TikTok"}]
        phone.apps["com.zhiliaoapp.musically"] = "TikTok"  # installed before the block was set up
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        row = self.never_rows()["com.zhiliaoapp.musically"]
        self.assertIn("Uninstall it to stop it", row.get_subtitle())
        row.uninstall.click()
        self.dialogs[-1].emit("response", "uninstall")
        self.pump(lambda: "com.zhiliaoapp.musically" in phone.placeholders and not self.win.placing,
                  what="uninstall, then placeholder")
        self.assertNotIn("com.zhiliaoapp.musically", phone.apps)
        self.assertIn("TikTok uninstalled", self.toasts)
        self.assertFalse(phone.install("com.zhiliaoapp.musically", "TikTok"))

    def test_uninstall_needs_confirmation(self):
        phone = self.ready_phone()
        phone.install_blocks = [{"pkg": "com.zhiliaoapp.musically", "name": "TikTok"}]
        phone.apps["com.zhiliaoapp.musically"] = "TikTok"
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        self.never_rows()["com.zhiliaoapp.musically"].uninstall.click()
        self.dialogs[-1].emit("response", "cancel")
        self.pump(lambda: False, timeout=0.3, fail=False)
        self.assertIn("com.zhiliaoapp.musically", phone.apps)

    def test_release_removes_the_placeholder(self):
        phone = self.ready_phone()
        phone.install_blocks = [{"pkg": "com.zhiliaoapp.musically", "name": "TikTok"}]
        self.open(phone)
        self.wait_page("main")
        self.pump(lambda: phone.placeholders and not self.win.placing, what="placeholder")
        self.never_rows()["com.zhiliaoapp.musically"].release.click()
        self.pump(lambda: not phone.install_blocks and not self.win.working, what="release")
        self.assertEqual(phone.placeholders, set())
        self.assertTrue(phone.install("com.zhiliaoapp.musically", "TikTok"), "installs normally again")

    def test_release_brings_a_caught_app_back(self):
        phone = self.ready_phone()
        phone.install_blocks = [{"pkg": "com.zhiliaoapp.musically", "name": "TikTok"}]
        phone.install("com.zhiliaoapp.musically", "TikTok")  # installed before any placeholder
        self.open(phone)
        self.wait_page("main")
        self.never_rows()["com.zhiliaoapp.musically"].release.click()
        self.pump(lambda: not phone.install_blocks and not self.win.working, what="release")
        self.assertEqual(phone.blocked, set())
        self.assertEqual(self.toasts[-1], "TikTok released: it can be installed and used again")
        self.pump(lambda: "com.zhiliaoapp.musically" in self.win.rows, what="app back in the list")
        self.assertEqual(self.never_rows(), {})

    def test_add_from_suggestions(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.on_add_install_block()
        d = self.dialogs[-1]
        buttons = [b for b in d.get_extra_child().findChildren(QPushButton) if b.toolTip() == "Add TikTok"]
        buttons[0].click()
        self.pump(lambda: self.phone.install_blocks and not self.win.working, what="add")
        self.assertEqual(self.phone.install_blocks, [{"pkg": "com.zhiliaoapp.musically", "name": "TikTok"}])
        self.assertIn("TikTok added to Never allow", self.toasts)
        self.pump(lambda: self.phone.placeholders == {"com.zhiliaoapp.musically"}, what="placeholder")

    def test_add_by_play_store_link(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.on_add_install_block()
        d = self.dialogs[-1]
        d.entry.setText("https://play.google.com/store/apps/details?id=com.example.doomscroll&hl=en")
        d.emit("response", "add")
        self.pump(lambda: self.phone.install_blocks and not self.win.working, what="add")
        self.assertEqual(self.phone.install_blocks[0]["pkg"], "com.example.doomscroll")

    def test_add_rejects_nonsense(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.on_add_install_block()
        self.dialogs[-1].entry.setText("just some words")
        self.dialogs[-1].emit("response", "add")
        self.assertIn("doesn't look like an app", self.errors[0][0])
        self.assertEqual(self.phone.install_blocks, [])

    def test_messenger_installs_fine_when_facebook_is_blocked(self):
        phone = self.ready_phone()
        phone.install_blocks = [{"pkg": "com.facebook.katana", "name": "Facebook"}]
        self.open(phone)
        self.wait_page("main")
        self.pump(lambda: "com.facebook.katana" in phone.placeholders and not self.win.placing, what="placeholder")
        self.assertTrue(phone.install("com.facebook.orca", "Messenger"))
        self.assertFalse(phone.install("com.facebook.katana", "Facebook"))
        self.assertNotIn("com.facebook.orca", phone.blocked)

    def test_anchored_app_not_on_the_phone_cant_be_installed(self):
        phone = self.ready_phone()
        phone.selected, phone.shifted = {"com.zhiliaoapp.musically", INSTAGRAM}, True
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        row = self.win.rows["com.zhiliaoapp.musically"]
        self.assertEqual(row.label, "TikTok")
        self.assertEqual(row.get_subtitle(), "Not on your phone · can't be installed while anchored")
        self.assertEqual(self.section_of("com.zhiliaoapp.musically"), "picked")
        phone.install("com.zhiliaoapp.musically", "TikTok")
        self.assertIn("com.zhiliaoapp.musically", phone.blocked)

    # ---- list filtering ----
    def visible_rows(self):
        return sorted(pkg for pkg, row in self.win.rows.items() if shown(row))

    def test_search_filters_by_name_and_package(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.search.setText("you")
        self.pump(lambda: self.visible_rows() == [YOUTUBE], what="search filter")
        self.win.search.setText("instagram.android")
        self.pump(lambda: self.visible_rows() == [INSTAGRAM], what="search filter")

    def test_search_covers_both_sections(self):
        self.open_shifted(INSTAGRAM)
        self.win.search.setText("o")  # matches apps in both sections
        self.pump(lambda: INSTAGRAM in self.visible_rows() and YOUTUBE in self.visible_rows(), what="search")
        self.win.search.setText("zzz")
        self.pump(lambda: self.visible_rows() == [], what="search")
        self.assertEqual(self.win.picked_section.empty.text(), "No apps match")
        self.assertTrue(shown(self.win.picked_section.empty))
        self.win.search.setText("")
        self.pump(lambda: len(self.visible_rows()) == len(self.win.rows), what="search reset")
        self.assertIn("Nothing anchored", self.win.picked_section.empty_text)

    def click_header(self, section):
        QTest.mouseClick(section.header, Qt.LeftButton)

    def test_sections_fold_and_unfold(self):
        self.open_shifted(INSTAGRAM)
        for section in (self.win.picked_section, self.win.other_section):
            self.assertTrue(section.is_open, "open at first")
            self.click_header(section)
            self.assertFalse(section.is_open, "folded")
            self.assertTrue(section.rows and all(not r.isVisibleTo(section) for r in section.rows),
                            "its apps are hidden")
            self.assertTrue(section.header.isVisibleTo(section), "the header stays")
            self.click_header(section)
            self.assertTrue(section.is_open, "open again")

    def test_sections_look_like_never_allow(self):
        self.open_shifted(INSTAGRAM)
        icons = {s.icon_name for s in (self.win.picked_section, self.win.other_section, self.win.never_section)}
        self.assertEqual(icons, {"anchor", "grid", "block"})
        self.assertEqual(self.win.picked_section.title_label.text(), "Anchored apps (1)")
        self.assertIn("Tap Release", self.win.picked_section.hint_label.text())

    def test_search_opens_folded_sections(self):
        self.open_shifted(INSTAGRAM)
        self.click_header(self.win.other_section)
        self.win.search.setText("you")
        self.pump(lambda: self.win.other_section.is_open, what="unfold on search")

    def test_sections_are_alphabetical(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        order = [r.label for r in self.win.other_section.rows]
        self.assertEqual(order, sorted(order, key=str.casefold))
        self.toggle(YOUTUBE)
        self.toggle(INSTAGRAM)
        self.wait_synced()
        self.pump(lambda: len(self.win.picked_section.rows) == 2, what="rows moved")
        self.assertEqual([r.label for r in self.win.picked_section.rows], ["Instagram", "YouTube"])

    # ---- free version: one phone per computer ----
    def claim_other_phone(self):
        ac.KeyStore().claim({"device_id": "0ther0phone00000", "model": "Samsung Galaxy S24"})

    def test_first_phone_is_kept_by_this_computer(self):
        self.open(FakePhone())
        self.wait_page("setup")
        self.win.setup_button.click()
        self.wait_page("main")
        self.assertEqual(ac.KeyStore().phone()["id"], self.phone.device_id)

    def test_second_phone_setup_is_refused(self):
        self.claim_other_phone()
        self.open(FakePhone())
        self.wait_page("setup")
        self.win.setup_button.click()
        self.pump(lambda: self.dialogs, what="limit dialog")
        self.assertEqual(self.dialogs[-1].get_heading(), "The free version works with one phone")
        self.assertIn("Samsung Galaxy S24", self.dialogs[-1].get_body())
        self.assertFalse(self.phone.owner)
        self.assertIsNone(self.phone.token_hash)

    def test_forgetting_the_other_phone_lets_this_one_set_up_with_a_new_key(self):
        self.claim_other_phone()
        self.open(FakePhone())
        self.wait_page("setup")
        self.win.setup_button.click()
        self.pump(lambda: self.dialogs, what="limit dialog")
        self.dialogs[-1].emit("response", "forget")
        self.wait_page("main")
        new_token = ac.KeyStore().token
        self.assertNotEqual(new_token, self.token)
        self.assertEqual(self.phone.token_hash, FakePhone._hash(new_token))
        self.assertEqual(ac.KeyStore().phone()["id"], self.phone.device_id)

    def test_second_phone_already_paired_shows_limit_page(self):
        self.claim_other_phone()
        self.open(self.ready_phone())
        self.wait_page("limit")
        self.assertIn("Samsung Galaxy S24", self.win.limit_page.get_description())

    def test_removing_anchor_frees_the_phone_slot(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.assertIsNotNone(ac.KeyStore().phone())
        self.win.on_remove()
        self.dialogs[-1].emit("response", "remove")
        self.wait_page("setup")
        self.assertIsNone(ac.KeyStore().phone())

    def test_removing_the_extra_phone_keeps_the_slot(self):
        self.claim_other_phone()
        self.open(self.ready_phone())
        self.wait_page("limit")
        self.win.on_remove()
        self.dialogs[-1].emit("response", "remove")
        self.pump(lambda: not self.phone.installed, what="uninstall")
        self.assertEqual(ac.KeyStore().phone()["id"], "0ther0phone00000")

    def check_updates(self, result=None, error=None, press=None):
        opened = []
        with mock.patch.object(anchor.updates, "check", return_value=result, side_effect=error), \
                mock.patch.object(anchor.QDesktopServices, "openUrl", lambda url: opened.append(url.toString())):
            self.win.activate_action("win.updates")
            self.pump(lambda: self.dialogs or self.errors, what="update answer")
            if press:
                self.dialogs[-1].emit("response", press)
        return opened

    def test_check_for_updates_when_up_to_date(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.assertEqual(self.check_updates(anchor.updates.CURRENT), [])
        self.assertEqual(self.dialogs[-1].get_heading(), "You're up to date")
        self.assertIn("Checking for updates…", self.toasts)

    def test_check_for_updates_offers_the_download(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        opened = self.check_updates(anchor.updates.AVAILABLE, press="download")
        self.assertEqual(opened, ["https://github.com/medpaf/anchor/releases/tag/windows"])

    def update_on_windows(self, download_error=None):
        """Check for updates… → Update, with the download, installer and quitting replaced."""
        self.open(self.ready_phone())
        self.wait_page("main")
        installer = os.path.join(self.tmp.name, "anchor-win.exe")
        with mock.patch.object(anchor.AnchorWindow, "can_update_itself", lambda win: True), \
                mock.patch.object(anchor.updates, "check", return_value=anchor.updates.AVAILABLE), \
                mock.patch.object(anchor.updates, "download", return_value=installer,
                                  side_effect=download_error) as download, \
                mock.patch.object(plat, "run_update_installer") as run_installer, \
                mock.patch.object(QApplication, "quit") as quit_:
            self.win.activate_action("win.updates")
            self.pump(lambda: self.dialogs, what="update answer")
            self.assertIn("installs it over this one and restarts", self.dialogs[-1].get_body())
            self.dialogs[-1].emit("response", "update")
            self.pump(lambda: quit_.called or self.errors, what="update finished")
        return download, run_installer, quit_, installer

    def test_update_downloads_the_installer_and_closes_anchor(self):
        download, run_installer, quit_, installer = self.update_on_windows()
        download.assert_called_once_with("windows", "anchor-win.exe")
        run_installer.assert_called_once_with(installer)
        quit_.assert_called_once()
        self.assertTrue(os.path.isdir(os.path.join(self.tmp.name, "anchor")), "the key stays")

    def test_update_download_failing_is_explained(self):
        _download, run_installer, quit_, _installer = self.update_on_windows(download_error=OSError("offline"))
        self.assertEqual(self.errors[-1][0], "Couldn't update Anchor")
        run_installer.assert_not_called()
        quit_.assert_not_called()

    def test_a_copy_run_from_source_opens_the_download_page(self):
        self.open(self.ready_phone())
        self.assertFalse(self.win.can_update_itself())

    def test_check_for_updates_not_now_opens_nothing(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.assertEqual(self.check_updates(anchor.updates.AVAILABLE, press="later"), [])

    def test_check_for_updates_on_a_copy_not_built_by_github(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        opened = self.check_updates(anchor.updates.UNKNOWN, press="download")
        self.assertEqual(self.dialogs[-1].get_heading(), "Can't tell which version this is")
        self.assertEqual(opened, ["https://github.com/medpaf/anchor/releases/tag/windows"])

    def test_check_for_updates_without_internet(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.check_updates(error=OSError("no network"))
        self.assertEqual(self.errors[-1][0], "Couldn't check for updates")

    def test_buy_me_a_coffee_opens_the_sponsors_page(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        opened = []
        with mock.patch.object(anchor.QDesktopServices, "openUrl", lambda url: opened.append(url.toString())):
            self.win.activate_action("win.donate", None)
        self.assertEqual(opened, ["https://github.com/sponsors/medpaf"])

    def test_menu_has_every_action(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        texts = [a.text() for a in self.win.menu.actions() if not a.isSeparator()]
        self.assertEqual(texts, ["Refresh", "Backup key…", "Use a backup key…", "Remove Anchor from phone…",
                                 "Check for updates…", "Buy me a coffee…", "About Anchor"])

    def test_window_title_shows_the_version(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.assertEqual(self.win.windowTitle(), "Anchor", "the title bar, with nothing added")
        self.assertEqual(self.win.title_label.text(), "Anchor - Free")

    def test_about_shows_edition_and_developer(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.activate_action("win.about", None)
        about = self.dialogs[-1]
        self.assertEqual(about.get_application_name(), "Anchor - Free")
        texts = [lbl.text() for lbl in about.panel.findChildren(widgets.QLabel)]
        self.assertNotIn(anchor.VERSION, texts, "no version under the title")
        self.assertEqual(texts.count("Paulo Medeiros"), 1, "the name only in Developed by")
        self.assertEqual(about.get_website(), "https://github.com/medpaf/anchor")
        self.assertEqual(about.site.text(), "GitHub repository")

    # ---- removal ----
    def test_remove_unblocks_and_uninstalls(self):
        phone = self.ready_phone()
        phone.selected, phone.shifted = {INSTAGRAM}, True
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        self.win.on_remove()
        self.dialogs[-1].emit("response", "remove")
        self.pump(lambda: not phone.installed, what="uninstall")
        self.assertEqual(phone.blocked, set())
        self.wait_page("setup")

    def test_see_through_icons_keep_their_colour(self):
        # Qt's SVG renderer can't read CSS rgba(): such icons used to come out black.
        image = widgets.symbol("phone", "rgba(238, 234, 247, 0.42)", 24).toImage()
        colours = {image.pixelColor(x, y).name() for x in range(image.width()) for y in range(image.height())
                   if image.pixelColor(x, y).alpha() > 0}
        self.assertTrue(colours and all(c != "#000000" for c in colours), colours)

    def test_narrow_window_keeps_everything_inside(self):
        self.open_shifted(INSTAGRAM)
        self.win.resize(self.win.minimumWidth(), 700)
        self.pump(lambda: False, timeout=0.3, fail=False)
        page = self.win.pages["main"]
        self.assertLessEqual(page.widget().width(), page.viewport().width(), "no sideways scrolling")
        self.assertEqual(self.win.rows[INSTAGRAM].uninstall_button.text(), "", "Uninstall is an icon")
        self.assertGreater(self.win.rows[INSTAGRAM].title_label.width(), 60, "the app's name has room")
        self.win.resize(580, 780)
        self.pump(lambda: False, timeout=0.3, fail=False)
        self.assertEqual(self.win.rows[INSTAGRAM].uninstall_button.text(), "Uninstall")

    def test_connect_page_shows_all_its_text(self):
        self.open(devices=[])
        self.wait_page("nophone")
        self.pump(lambda: False, timeout=0.3, fail=False)
        text = self.win.pages["nophone"].text
        self.assertGreaterEqual(text.height(), text.heightForWidth(text.width()), "wrapped text isn't cut off")

    # ---- dialogs ----
    def test_long_messages_fit_in_their_dialog(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        REAL_ERROR_DIALOG(self.win, "Couldn't do that", "A long explanation. " * 30)
        d = self.dialogs[-1]
        d.show()  # really on screen (the tests normally only collect dialogs), so Qt lays it out
        d._place()
        self.pump(lambda: False, timeout=0.3, fail=False)
        body = d.body
        self.assertGreaterEqual(body.height(), body.heightForWidth(body.width()), "the whole message shows")
        self.assertGreaterEqual(d.panel.height(), d.panel.layout().totalHeightForWidth(d.panel.width()))

    def test_escape_closes_a_dialog_with_its_cancel_answer(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.on_remove()
        d = self.dialogs[-1]
        answers = []
        d.response.connect(answers.append)
        QTest.keyClick(d, Qt.Key_Escape)
        self.assertEqual(answers, ["cancel"])
        self.assertTrue(self.phone.installed)


if __name__ == "__main__":
    unittest.main()
