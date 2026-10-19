"""Drives the real Anchor window against a fake phone. Needs a display (skipped without one)."""

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from fakes import FakeAdb, FakePhone, ac

try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gio, GLib, Gtk

    HAVE_DISPLAY = Gtk.init_check()
except (ImportError, ValueError):
    HAVE_DISPLAY = False

if HAVE_DISPLAY:
    import anchor

    REAL_ERROR_DIALOG = anchor.AnchorWindow.error_dialog
    REAL_TOAST = anchor.AnchorWindow.toast
    REAL_PASSWORD_CHECK = anchor.system_password_check

INSTAGRAM, YOUTUBE, DIALER = "com.instagram.android", "com.google.android.youtube", "com.google.android.dialer"
REDDIT = "com.reddit.frontpage"


@unittest.skipUnless(HAVE_DISPLAY, "needs a graphical display")
class GuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Adw.init()
        cls.app = Adw.Application(application_id="app.anchor.Tests", flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)
        # Making a placeholder signing key takes a few seconds; make one for the whole run.
        cls.key_tmp = tempfile.TemporaryDirectory()
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": cls.key_tmp.name}):
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
            mock.patch.dict(os.environ, {"XDG_DATA_HOME": self.tmp.name}),
            # GLib reads its data folder once at start-up and ignores XDG_DATA_HOME after that: patch the
            # functions too, so nothing a test does can ever reach the real ~/.local/share/anchor.
            mock.patch.object(anchor.GLib, "get_user_data_dir", return_value=self.tmp.name),
            mock.patch.object(anchor.Path, "home", return_value=Path(self.tmp.name)),
            mock.patch.object(anchor.ac, "find_adb", return_value="/fake/adb"),
            mock.patch.object(anchor.ac, "Adb", side_effect=lambda path: self.adb),
            # Tests trigger polls by hand instead of every 2 seconds.
            mock.patch.object(anchor.GLib, "timeout_add_seconds", return_value=0),
            mock.patch.object(anchor.AnchorWindow, "error_dialog",
                              lambda win, title, body, details="": self.errors.append((title, body))),
            mock.patch.object(anchor.AnchorWindow, "toast",
                              lambda win, text, timeout=3: self.toasts.append(text)),
            mock.patch.object(Adw.AlertDialog, "present", lambda d, parent: self.dialogs.append(d)),
            mock.patch.object(Adw.Dialog, "present", lambda d, parent: self.dialogs.append(d)),
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
            self.win.destroy()
            self.pump(lambda: False, timeout=0.05, fail=False)

    # ---- helpers ----
    def open(self, phone=None, devices=None):
        self.phone = phone or FakePhone()
        self.adb = FakeAdb(self.phone, devices)
        self.win = anchor.AnchorWindow(self.app)
        return self.win

    def pump(self, cond, timeout=15.0, fail=True, what="condition"):
        ctx = GLib.MainContext.default()
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            while ctx.pending():
                ctx.iteration(False)
            if cond():
                return True
            time.sleep(0.01)
        if fail:
            self.fail(f"timed out waiting for {what}")
        return False

    def page(self):
        return self.win.stack.get_visible_child_name()

    def wait_page(self, name, timeout=15.0):
        self.pump(lambda: self.page() == name, timeout, what=f"page '{name}' (now '{self.page()}')")

    def ready_phone(self, **kw):
        return FakePhone(**kw).ready(self.token)

    def toggle(self, pkg, on=True):
        """Clicks the app's Anchor (on) or Release (off) button if it isn't in that state already, and says
        yes when an app that came with the phone asks first."""
        if (pkg in self.win.selected) != on:
            asked = len(self.dialogs)
            self.win.rows[pkg].anchor_button.emit("clicked")
            if len(self.dialogs) > asked and self.dialogs[-1].get_heading().startswith("Anchor "):
                self.dialogs[-1].emit("response", "anchor")

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

    # ---- setup ----
    def test_fresh_phone_goes_through_setup(self):
        self.open(FakePhone())
        self.wait_page("setup")
        self.assertEqual(self.win.setup_button.get_label(), "Set up phone")
        self.win.setup_button.emit("clicked")
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
        self.win.setup_button.emit("clicked")
        self.pump(lambda: self.errors, what="error dialog")
        self.assertIn("Remove the accounts", self.errors[0][0])
        steps = [s.get_visible_child_name() for s in self.win.step_rows]
        self.assertEqual(steps, ["done", "todo", "todo"])
        self.assertTrue(self.win.setup_button.get_sensitive())
        # The user removes the accounts and tries again.
        phone.dpm_output = None
        self.win.setup_button.emit("clicked")
        self.wait_page("main")

    def test_accounts_error_names_the_apps(self):
        phone = FakePhone(apps=[("com.meetup", "Meetup")])
        phone.accounts = [("me@example.com", "com.meetup.auth", "com.meetup")]
        self.open(phone)
        self.wait_page("setup")
        self.win.setup_button.emit("clicked")
        self.pump(lambda: self.errors, what="error dialog")
        title, body = self.errors[0]
        self.assertIn("Remove the accounts", title)
        self.assertIn("Meetup: me@example.com", body)

    def test_long_error_details_stay_inside_the_window(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        trace = "java.lang.IllegalStateException: " + "x" * 400 + "\n" + "\tat com.android.Foo(Foo.java:1)\n" * 80
        REAL_ERROR_DIALOG(self.win, "Title", "Body", trace)
        expander = self.dialogs[-1].get_extra_child()
        expander.set_expanded(True)
        _, nat_w, _, _ = expander.measure(Gtk.Orientation.HORIZONTAL, -1)
        _, nat_h, _, _ = expander.measure(Gtk.Orientation.VERTICAL, 400)
        self.assertLess(nat_w, 400, "details must wrap instead of widening the dialog")
        self.assertLess(nat_h, 300, "details must scroll instead of growing the dialog")

    def test_half_set_up_phone_offers_to_continue(self):
        phone = FakePhone()
        phone.installed = True
        self.open(phone)
        self.wait_page("setup")
        self.assertEqual(self.win.setup_button.get_label(), "Continue setup")
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
        dialog.get_extra_child().set_text(ac.KeyStore.format(other))
        dialog.emit("response", "use")
        self.wait_page("main")
        self.assertEqual(ac.KeyStore().token, other)

    def test_bad_backup_key_is_rejected(self):
        self.open(FakePhone().ready("f" * 32))
        self.wait_page("foreign")
        self.win.on_import()
        self.dialogs[-1].get_extra_child().set_text("not a key")
        self.dialogs[-1].emit("response", "use")
        self.assertIn("doesn't look right", self.errors[0][0])
        self.assertEqual(ac.KeyStore().token, self.token)

    def test_backup_key_dialog_shows_formatted_key(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.on_backup()
        self.assertEqual(self.dialogs[-1].get_extra_child().get_label(), ac.KeyStore.format(self.token))

    # ---- shifting ----
    def test_lists_phone_apps(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.assertEqual(set(self.win.rows), {p for p, _ in FakePhone().apps.items()})
        self.assertEqual(self.win.title_widget.get_subtitle(), "Google Pixel 8")

    def open_shifted(self, *pkgs):
        phone = self.ready_phone()
        phone.selected, phone.shifted = set(pkgs), True
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        return phone

    def section_of(self, pkg):
        parent = self.win.rows[pkg].get_parent()
        return {self.win.picked_list: "picked", self.win.other_list: "other"}.get(parent)

    def test_nothing_anchored_at_first(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.assertEqual(self.win.hero_title.get_label(), "Not anchored")
        self.assertEqual(self.win.hero_title.get_label(), "Not anchored")
        self.assertFalse(self.win.hero_button.get_visible(), "nothing to release")
        self.assertEqual({r.anchor_button.get_label() for r in self.win.rows.values()}, {"Anchor"})
        self.assertFalse(self.win.picked_title.section.get_visible(), "no empty Anchored section")
        self.assertEqual(self.win.other_title.get_label(), f"Your apps ({len(self.win.rows)})")

    def test_anchor_one_app_hides_it_right_away(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.toggle(INSTAGRAM)
        self.assertEqual(self.win.rows[INSTAGRAM].get_subtitle(), "Hiding…")
        self.wait_synced()
        self.assertEqual((self.phone.mode(), self.phone.blocked), ("manual", {INSTAGRAM}))
        row = self.win.rows[INSTAGRAM]
        self.assertEqual((row.anchor_button.get_label(), row.get_subtitle()), ("Release", "Hidden"))
        self.pump(lambda: self.section_of(INSTAGRAM) == "picked", what="row move")
        self.assertEqual(self.win.picked_title.get_label(), "Anchored apps (1)")
        self.assertEqual(self.win.hero_title.get_label(), "Anchored")
        self.assertEqual(self.win.hero_button.get_label(), "Release all")
        self.assertEqual(self.win.hero_icon.get_icon_name(), "anchor-orb-on", "the logo lights up while anchored")
        self.assertEqual(self.toasts[-1], "Instagram anchored: hidden from your phone")

    def test_release_one_app(self):
        phone = self.open_shifted(INSTAGRAM, YOUTUBE)
        self.assertEqual(self.win.rows[YOUTUBE].anchor_button.get_label(), "Release")
        self.toggle(YOUTUBE, False)
        self.assertEqual(self.win.rows[YOUTUBE].get_subtitle(), "Bringing back…")
        self.wait_synced()
        self.assertEqual((phone.mode(), phone.blocked), ("manual", {INSTAGRAM}))
        self.pump(lambda: self.section_of(YOUTUBE) == "other", what="row move")
        self.assertEqual(self.win.rows[YOUTUBE].anchor_button.get_label(), "Anchor")
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
        self.assertEqual(self.win.hero_title.get_label(), "On schedule")

    def test_release_all(self):
        phone = self.open_shifted(INSTAGRAM, YOUTUBE)
        self.win.hero_button.emit("clicked")
        self.pump(lambda: phone.mode() is None and not self.win.working, what="release all")
        self.assertEqual((phone.blocked, phone.selected), (set(), set()))
        self.assertEqual(self.toasts[-1], "Released · all apps are back")
        self.assertEqual(self.win.hero_title.get_label(), "Not anchored")
        self.assertEqual(self.win.rows[INSTAGRAM].anchor_button.get_label(), "Anchor")

    def test_release_all_asks_for_the_password_first(self):
        phone = self.open_shifted(INSTAGRAM, YOUTUBE)
        for answer, message in (("cancelled", "Release all cancelled"), ("denied", "Password not accepted")):
            self.password_answer = answer
            self.win.hero_button.emit("clicked")
            self.pump(lambda: any(message in t for t in self.toasts), what=answer)
            self.assertEqual(phone.blocked, {INSTAGRAM, YOUTUBE}, f"{answer}: still anchored")
            self.assertTrue(self.win.hero_button.get_sensitive())
        self.password_answer = "ok"
        self.win.hero_button.emit("clicked")
        self.pump(lambda: phone.mode() is None and not self.win.working, what="release after password")
        self.assertEqual(phone.blocked, set())

    def test_release_all_without_a_password_prompt(self):
        phone = self.open_shifted(INSTAGRAM)
        self.password_answer = "missing"
        self.win.hero_button.emit("clicked")
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
        self.assertEqual(self.section_of(DIALER), "picked")
        self.assertEqual(self.toasts[-1], "Phone can't be hidden (protected by Android)")

    def test_anchor_started_on_phone_is_picked_up(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        phone.selected, phone.shifted = {INSTAGRAM}, True  # the user pressed "Anchor now" on the phone
        phone._apply()
        self.win.poll()
        self.pump(lambda: self.win.hero_title.get_label() == "Anchored", what="status refresh")
        self.assertEqual(self.win.rows[INSTAGRAM].anchor_button.get_label(), "Release")

    def test_old_list_from_before_buttons_is_cleared(self):
        phone = self.ready_phone()
        phone.selected = {INSTAGRAM}  # saved, but not anchored
        self.open(phone)
        self.wait_page("main")
        self.assertEqual(phone.selected, set())
        self.assertEqual(self.win.rows[INSTAGRAM].anchor_button.get_label(), "Anchor")

    def test_phone_unplugged_while_anchoring_shows_error(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        with mock.patch.object(ac.Agent, "shift", side_effect=ac.AdbError("device not found")):
            self.toggle(INSTAGRAM)
            self.pump(lambda: any("Couldn't reach the phone" in t for t in self.toasts), what="error")
        self.pump(lambda: self.win.rows[INSTAGRAM].anchor_button.get_label() == "Anchor", what="undone")

    # ---- auto-release ----
    def test_timer_running_out_releases_the_apps(self):
        phone = self.ready_phone()
        phone.selected, phone.until = {INSTAGRAM}, FakePhone.now() + 600
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        self.assertEqual(self.win.rows[INSTAGRAM].anchor_button.get_label(), "Release")
        time.sleep(0.7)
        self.win.poll()
        self.pump(lambda: self.win.hero_title.get_label() == "Not anchored", what="timer end")
        self.assertEqual(self.win.rows[INSTAGRAM].anchor_button.get_label(), "Anchor")

    def test_release_all_ends_a_timer_early(self):
        phone = self.ready_phone()
        phone.selected, phone.until = {INSTAGRAM}, FakePhone.now() + 3_600_000
        phone._apply()
        self.open(phone)
        self.wait_page("main")
        self.win.hero_button.emit("clicked")
        self.pump(lambda: phone.mode() is None and not self.win.working, what="release")
        self.assertEqual(phone.blocked, set())

    # ---- uninstall ----
    def test_uninstall_button_only_on_apps_that_can_be_uninstalled(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.assertIsNone(self.win.rows[YOUTUBE].uninstall_button, "came with the phone: anchor it instead")
        self.assertIsNotNone(self.win.rows[INSTAGRAM].uninstall_button)

    def test_uninstall_an_app(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        self.win.rows[INSTAGRAM].uninstall_button.emit("clicked")
        self.assertIn("Uninstall Instagram?", self.dialogs[-1].get_heading())
        self.dialogs[-1].emit("response", "uninstall")
        self.pump(lambda: INSTAGRAM not in self.win.rows, what="uninstall")
        self.assertNotIn(INSTAGRAM, phone.apps)
        self.assertIn("Instagram uninstalled", self.toasts)
        self.assertEqual(self.win.other_title.get_label(), f"Your apps ({len(self.win.rows)})", "count updated")

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
        self.win.open_app_details({"pkg": DIALER, "label": "Phone"})
        self.assertIsNone(self.win.details.uninstall, "not for apps the phone needs")
        self.win.open_app_details({"pkg": INSTAGRAM, "label": "Instagram"})
        self.win.details.uninstall.emit("clicked")
        self.assertEqual(self.dialogs[-1].get_heading(), "Uninstall Instagram?")
        self.dialogs[-1].emit("response", "uninstall")
        self.pump(lambda: INSTAGRAM not in self.win.rows, what="uninstall")
        self.assertNotIn(INSTAGRAM, phone.apps)

    def test_details_show_a_spinner_until_they_load(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.open_app_details({"pkg": INSTAGRAM, "label": "Instagram"})
        d = self.win.details
        self.assertTrue(d.loading_group.get_visible(), "a spinner first")
        self.assertFalse(d.about.get_visible(), "no half-empty cards meanwhile")
        self.pump(lambda: d.page_widgets, what="details")
        self.assertFalse(d.loading_group.get_visible())
        self.assertTrue(d.about.get_visible() and d.perms.get_visible() and d.uninstall.get_visible(),
                        "then everything at once")

    def test_backup_key_saves_as_a_pdf(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        path = os.path.join(self.tmp.name, "Anchor backup key.pdf")
        self.win.save_key_pdf(path)
        with open(path, "rb") as f:
            self.assertEqual(f.read(5), b"%PDF-")
        self.assertIn("Backup key saved as Anchor backup key.pdf", self.toasts)

    def test_backup_key_pdf_failure_is_explained(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.save_key_pdf(os.path.join(self.tmp.name, "no-such-folder", "key.pdf"))
        self.assertEqual(self.errors[-1][0], "Couldn't save the backup key")

    def test_anchoring_a_system_app_asks_first(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        self.win.on_anchor_clicked(YOUTUBE)
        self.assertEqual(self.dialogs[-1].get_heading(), "Anchor YouTube?")
        self.assertIn("came with your phone", self.dialogs[-1].get_body())
        self.dialogs[-1].emit("response", "cancel")
        self.pump(lambda: False, timeout=0.5, fail=False)
        self.assertNotIn(YOUTUBE, phone.blocked, "cancelled: nothing hidden")
        self.win.on_anchor_clicked(YOUTUBE)
        self.dialogs[-1].emit("response", "anchor")
        self.pump(lambda: YOUTUBE in phone.blocked and not self.win.working, what="anchored")

    def test_anchoring_your_own_app_doesnt_ask(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        before = len(self.dialogs)
        self.win.on_anchor_clicked(INSTAGRAM)
        self.pump(lambda: INSTAGRAM in phone.blocked and not self.win.working, what="anchored")
        self.assertEqual(len(self.dialogs), before)

    def test_uninstall_needs_confirmation_in_the_list(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        self.win.rows[INSTAGRAM].uninstall_button.emit("clicked")
        self.dialogs[-1].emit("response", "cancel")
        self.pump(lambda: False, timeout=0.3, fail=False)
        self.assertIn(INSTAGRAM, phone.apps)

    def test_uninstalling_a_never_allowed_app_puts_the_placeholder_in(self):
        phone = self.ready_phone()
        phone.install_blocks = [{"pkg": INSTAGRAM, "name": "Instagram"}]
        phone.kept = {INSTAGRAM}  # it was on the phone before it was added
        self.open(phone)
        self.wait_page("main")
        self.win.rows[INSTAGRAM].uninstall_button.emit("clicked")
        self.dialogs[-1].emit("response", "uninstall")
        self.pump(lambda: INSTAGRAM in phone.placeholders and not self.win.placing, what="placeholder")
        self.assertFalse(phone.install(INSTAGRAM, "Instagram"))

    # ---- per-app schedules ----
    NIGHT = {"id": "n1", "name": "YouTube", "enabled": True, "days": [1, 2, 3, 4, 5, 6, 7],
             "start": "22:30", "end": "07:00", "packages": [YOUTUBE]}

    def spins(self, widget):
        found = []
        if isinstance(widget, Gtk.SpinButton):
            found.append(widget)
        child = widget.get_first_child()
        while child:
            found += self.spins(child)
            child = child.get_next_sibling()
        return found

    def window_rows(self):
        rows, row = [], self.win.app_dialog[2].get_first_child()
        while row:
            if isinstance(row, Adw.ActionRow):
                rows.append(row)
            row = row.get_next_sibling()
        return rows

    def add_window(self, pkg, days=None, start=(22, 30), end=(7, 0)):
        self.win.edit_window(pkg, None)
        d = self.dialogs[-1]
        if days is not None:
            for i, b in enumerate(d.day_buttons, start=1):
                b.set_active(i in days)
        for spin, value in zip(self.spins(d.get_extra_child()), [*start, *end]):
            spin.set_value(value)
        d.emit("response", "save")

    def test_every_app_has_a_schedule_button(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        for pkg, row in self.win.rows.items():
            self.assertIn(row.label, row.sched_button.get_tooltip_text())
        self.assertTrue(self.phone.background_allowed, "phone is allowed to wake up on time")

    def test_open_app_schedule_starts_empty(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.rows[YOUTUBE].sched_button.emit("clicked")
        self.assertEqual(self.dialogs[-1].get_heading(), "YouTube schedule")
        self.assertEqual([r.get_title() for r in self.window_rows()], ["Add a time"])

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
        self.assertTrue(self.win.rows[YOUTUBE].sched_button.has_css_class("accent"))
        self.assertEqual(self.win.rows[INSTAGRAM].get_subtitle(), INSTAGRAM)
        self.assertFalse(self.win.rows[INSTAGRAM].sched_button.has_css_class("accent"))

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
        self.win.edit_window(YOUTUBE, self.window_rows()[0].window)
        d = self.dialogs[-1]
        self.spins(d.get_extra_child())[2].set_value(8)
        d.emit("response", "save")
        self.pump(lambda: phone.schedules[0]["end"] == "08:00" and not self.win.working, what="edit")
        self.assertEqual(len(phone.schedules), 1)

    def test_delete_a_time(self):
        phone = self.ready_phone()
        phone.schedules = [dict(self.NIGHT)]
        self.open(phone)
        self.wait_page("main")
        self.win.open_app_schedule(YOUTUBE)
        self.window_rows()[0].delete.emit("clicked")
        self.pump(lambda: not phone.schedules and not self.win.working, what="delete")
        self.assertEqual([r.get_title() for r in self.window_rows()], ["Add a time"])
        self.assertEqual(self.win.rows[YOUTUBE].get_subtitle(), YOUTUBE)

    def test_switch_a_time_off(self):
        phone = self.ready_phone()
        phone.schedules = [dict(self.NIGHT)]
        self.open(phone)
        self.wait_page("main")
        self.win.open_app_schedule(YOUTUBE)
        self.window_rows()[0].switch.set_active(False)
        self.pump(lambda: not phone.schedules[0]["enabled"] and not self.win.working, what="switch off")
        self.assertEqual(self.win.rows[YOUTUBE].get_subtitle(), "Every day · 22:30–07:00 · Off")
        self.assertFalse(self.win.rows[YOUTUBE].sched_button.has_css_class("accent"))
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
        self.assertEqual(self.win.hero_title.get_label(), "On schedule")
        self.assertIn("YouTube is hidden by its schedule right now", self.win.hero_subtitle.get_label())
        self.assertTrue(self.win.rows[YOUTUBE].get_subtitle().startswith("Hidden by its schedule until "))
        self.assertTrue(self.win.pause_button.get_visible())
        self.assertFalse(self.win.hero_button.get_visible(), "nothing anchored by hand")
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
        self.win.pause_button.emit("clicked")
        self.pump(lambda: not phone.blocked and not self.win.working, what="pause")
        self.assertEqual(phone.paused, {"n1": end})
        self.assertIn("Scheduled apps are back · schedules paused until", self.toasts[-1])
        self.assertIn("Paused until", self.win.rows[YOUTUBE].get_subtitle())
        self.assertFalse(self.win.pause_button.get_visible())
        self.assertEqual(self.win.hero_title.get_label(), "Not anchored")

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
        self.assertIn("Release all also pauses that", self.win.hero_subtitle.get_label())
        self.win.hero_button.emit("clicked")
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

    def test_password_check_reads_pkexec_answers(self):
        real = REAL_PASSWORD_CHECK
        done = lambda code: subprocess.CompletedProcess([], code)
        with mock.patch.object(anchor.shutil, "which", return_value="/usr/bin/pkexec"):
            for code, answer in ((0, "ok"), (126, "cancelled"), (127, "denied"), (1, "denied")):
                with mock.patch.object(anchor.subprocess, "run", return_value=done(code)) as run:
                    self.assertEqual(real(), answer, code)
                self.assertEqual(run.call_args[0][0][0], "pkexec", "the system's own prompt")
            for installed, command in ((True, anchor.RELEASE_CHECK), (False, "/bin/true")):
                with mock.patch.object(anchor.os, "access", return_value=installed), \
                        mock.patch.object(anchor.subprocess, "run", return_value=done(0)) as run:
                    real()
                self.assertEqual(run.call_args[0][0][-1], command, "worded prompt only when its policy is installed")
        with mock.patch.object(anchor.shutil, "which", return_value=None):
            self.assertEqual(real(), "missing")

    # ---- app details ----
    def open_details(self, pkg):
        self.win.rows[pkg].emit("activated")
        d = self.dialogs[-1]
        self.pump(lambda: d.perm_rows or getattr(d, "perm_empty", None), what="details")
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
        self.assertEqual(about["Screen time today"], "25 min")
        self.assertEqual(about["Screen time, last 7 days"], "3 h 10 min")
        self.assertEqual(phone.blocked, set(), "clicking the row doesn't anchor")
        self.assertEqual(self.win.rows[INSTAGRAM].anchor_button.get_label(), "Anchor")
        self.assertEqual(sorted(r.get_title() for r in d.perm_rows.values()), ["Camera", "Microphone", "Notifications"])
        self.assertEqual(d.perm_rows["android.permission.CAMERA"].get_subtitle(), "Take pictures and videos")

    def test_grant_and_remove_a_permission(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        d = self.open_details(INSTAGRAM)
        d.perm_rows["android.permission.CAMERA"].set_active(True)
        self.pump(lambda: "android.permission.CAMERA" in phone.granted.get(INSTAGRAM, set()), what="grant")
        self.pump(lambda: d.perm_rows["android.permission.CAMERA"].get_sensitive(), what="row refreshed")
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
        self.assertTrue(all(not r.get_sensitive() for r in d.perm_rows.values()), "greyed out while anchored")
        self.assertIn("comes back when released", d.perm_rows["android.permission.CAMERA"].get_subtitle())
        self.assertIn("removed while Instagram is blocked", d.perms.get_description())
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
        self.assertEqual([d for d in self.dialogs if isinstance(d, Adw.Dialog) and not isinstance(d, Adw.AlertDialog)], [])

    # ---- Never allow ----
    def never_rows(self):
        return {row.pkg: row for row in self.win.never_children if hasattr(row, "pkg")}

    def test_never_allow_starts_empty_on_first_connect(self):
        phone = self.ready_phone()
        phone.install_blocks_set = False  # a phone Anchor never set a list on
        self.open(phone)
        self.wait_page("main")
        self.pump(lambda: False, timeout=0.5, fail=False)
        self.assertEqual(phone.install_blocks, [], "nothing is added by itself")
        self.assertEqual(phone.placeholders, set())
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
        row.uninstall.emit("clicked")
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
        self.never_rows()["com.zhiliaoapp.musically"].uninstall.emit("clicked")
        self.dialogs[-1].emit("response", "cancel")
        self.pump(lambda: False, timeout=0.3, fail=False)
        self.assertIn("com.zhiliaoapp.musically", phone.apps)

    def test_release_removes_the_placeholder(self):
        phone = self.ready_phone()
        phone.install_blocks = [{"pkg": "com.zhiliaoapp.musically", "name": "TikTok"}]
        self.open(phone)
        self.wait_page("main")
        self.pump(lambda: phone.placeholders and not self.win.placing, what="placeholder")
        self.never_rows()["com.zhiliaoapp.musically"].release.emit("clicked")
        self.pump(lambda: not phone.install_blocks and not self.win.working, what="release")
        self.assertEqual(phone.placeholders, set())
        self.assertTrue(phone.install("com.zhiliaoapp.musically", "TikTok"), "installs normally again")

    def test_release_brings_a_caught_app_back(self):
        phone = self.ready_phone()
        phone.install_blocks = [{"pkg": "com.zhiliaoapp.musically", "name": "TikTok"}]
        phone.install("com.zhiliaoapp.musically", "TikTok")  # installed before any placeholder
        self.open(phone)
        self.wait_page("main")
        self.never_rows()["com.zhiliaoapp.musically"].release.emit("clicked")
        self.pump(lambda: not phone.install_blocks and not self.win.working, what="release")
        self.assertEqual(phone.blocked, set())
        self.assertEqual(self.toasts[-1], "TikTok released: it can be installed and used again")
        self.pump(lambda: "com.zhiliaoapp.musically" in self.win.rows, what="app back in the list")
        self.assertEqual(self.never_rows(), {})

    def test_add_several_suggestions_at_once(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.on_add_install_block()
        d = self.dialogs[-1]
        d.picks["com.zhiliaoapp.musically"][1].set_active(True)
        d.picks["com.snapchat.android"][1].set_active(True)
        d.emit("response", "add")
        self.pump(lambda: len(self.phone.install_blocks) == 2 and not self.win.working, what="add")
        self.assertEqual({a["pkg"] for a in self.phone.install_blocks}, {"com.zhiliaoapp.musically", "com.snapchat.android"})
        self.assertIn("2 apps added to Never allow", self.toasts)
        self.pump(lambda: self.phone.placeholders == {"com.zhiliaoapp.musically", "com.snapchat.android"}, what="placeholders")

    def test_add_ticked_suggestions_and_a_link_together(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.on_add_install_block()
        d = self.dialogs[-1]
        d.picks["com.zhiliaoapp.musically"][1].set_active(True)
        d.entry.set_text("https://play.google.com/store/apps/details?id=com.example.doomscroll")
        d.emit("response", "add")
        self.pump(lambda: len(self.phone.install_blocks) == 2 and not self.win.working, what="add")
        self.assertEqual({a["pkg"] for a in self.phone.install_blocks}, {"com.zhiliaoapp.musically", "com.example.doomscroll"})

    def test_add_with_nothing_chosen_does_nothing(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.on_add_install_block()
        self.dialogs[-1].emit("response", "add")
        self.pump(lambda: False, timeout=0.3, fail=False)
        self.assertEqual(self.phone.install_blocks, [])
        self.assertEqual(self.errors, [])

    def test_add_by_play_store_link(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.on_add_install_block()
        d = self.dialogs[-1]
        d.entry.set_text("https://play.google.com/store/apps/details?id=com.example.doomscroll&hl=en")
        d.emit("response", "add")
        self.pump(lambda: self.phone.install_blocks and not self.win.working, what="add")
        self.assertEqual(self.phone.install_blocks[0]["pkg"], "com.example.doomscroll")

    def test_add_rejects_nonsense(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.on_add_install_block()
        self.dialogs[-1].entry.set_text("just some words")
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
        self.assertIs(row.get_parent(), self.win.picked_list)
        phone.install("com.zhiliaoapp.musically", "TikTok")
        self.assertIn("com.zhiliaoapp.musically", phone.blocked)

    def find_all(self, widget, cls):
        found = [widget] if isinstance(widget, cls) else []
        child = widget.get_first_child()
        while child:
            found += self.find_all(child, cls)
            child = child.get_next_sibling()
        return found

    # ---- list filtering ----
    def visible_rows(self):
        return sorted(pkg for pkg, row in self.win.rows.items() if row.get_child_visible())

    def test_search_filters_by_name_and_package(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.win.search.set_text("you")
        self.pump(lambda: self.visible_rows() == [YOUTUBE], what="search filter")
        self.win.search.set_text("instagram.android")
        self.pump(lambda: self.visible_rows() == [INSTAGRAM], what="search filter")

    def test_search_covers_both_sections(self):
        self.open_shifted(INSTAGRAM)
        self.win.search.set_text("o")  # matches apps in both sections
        self.pump(lambda: INSTAGRAM in self.visible_rows() and YOUTUBE in self.visible_rows(), what="search")
        self.win.search.set_text("zzz")
        self.pump(lambda: self.visible_rows() == [], what="search")
        self.assertEqual(self.win.picked_list.placeholder_label.get_label(), "No apps match")
        self.win.search.set_text("")
        self.pump(lambda: len(self.visible_rows()) == len(self.win.rows), what="search reset")
        self.assertIn("Nothing anchored", self.win.picked_list.empty_text)

    def test_sections_fold_and_unfold(self):
        self.open_shifted(INSTAGRAM)
        for rows in (self.win.picked_list, self.win.other_list):
            self.assertTrue(rows.is_open, "open at first")
            rows.header.emit("activated")
            self.assertFalse(rows.is_open, "folded")
            apps = [r for r in self.all_rows(rows) if not getattr(r, "is_header", False)]
            self.assertTrue(apps and all(not r.get_child_visible() for r in apps), "its apps are hidden")
            self.assertTrue(rows.header.get_child_visible(), "the header stays")
            rows.header.emit("activated")
            self.assertTrue(rows.is_open, "open again")

    def all_rows(self, listbox):
        out, row = [], listbox.get_first_child()
        while row:
            if isinstance(row, Gtk.ListBoxRow):
                out.append(row)
            row = row.get_next_sibling()
        return out

    def test_sections_look_like_never_allow(self):
        self.open_shifted(INSTAGRAM)
        for rows, icon in ((self.win.picked_list, "anchor-section"),
                           (self.win.other_list, "view-app-grid-symbolic")):
            first = self.all_rows(rows)[0]
            self.assertIs(first, rows.header, "the header is the card's first row")
            self.assertIsInstance(first, Adw.ActionRow)
            images = [w for w in self.find_all(first, Gtk.Image) if w.get_icon_name() == icon]
            self.assertTrue(images, f"{icon} on the header")
        self.assertEqual(self.win.picked_list.header.get_title(), "Anchored apps (1)")
        self.assertIn("Tap Release", self.win.picked_list.header.get_subtitle())

    def test_search_opens_folded_sections(self):
        self.open_shifted(INSTAGRAM)
        self.win.other_list.header.emit("activated")
        self.win.search.set_text("you")
        self.pump(lambda: self.win.other_list.is_open, what="unfold on search")

    def test_sections_are_alphabetical(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        order = []
        row = self.win.other_list.get_first_child()
        while row:
            if hasattr(row, "label"):
                order.append(row.label)
            row = row.get_next_sibling()
        self.assertEqual(order, sorted(order, key=str.casefold))

    # ---- free version: one phone per computer ----
    def claim_other_phone(self):
        ac.KeyStore().claim({"device_id": "0ther0phone00000", "model": "Samsung Galaxy S24"})

    def test_first_phone_is_kept_by_this_computer(self):
        self.open(FakePhone())
        self.wait_page("setup")
        self.win.setup_button.emit("clicked")
        self.wait_page("main")
        self.assertEqual(ac.KeyStore().phone()["id"], self.phone.device_id)

    def test_second_phone_setup_is_refused(self):
        self.claim_other_phone()
        self.open(FakePhone())
        self.wait_page("setup")
        self.win.setup_button.emit("clicked")
        self.pump(lambda: self.dialogs, what="limit dialog")
        self.assertEqual(self.dialogs[-1].get_heading(), "The free version works with one phone")
        self.assertIn("Samsung Galaxy S24", self.dialogs[-1].get_body())
        self.assertFalse(self.phone.owner)
        self.assertIsNone(self.phone.token_hash)

    def test_forgetting_the_other_phone_lets_this_one_set_up_with_a_new_key(self):
        self.claim_other_phone()
        self.open(FakePhone())
        self.wait_page("setup")
        self.win.setup_button.emit("clicked")
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
                mock.patch.object(Gtk.UriLauncher, "launch", lambda l, *a: opened.append(l.get_uri())):
            self.win.activate_action("win.updates", None)
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
        self.assertEqual(self.dialogs[-1].get_heading(), "A new version of Anchor is available")
        self.assertEqual(opened, ["https://github.com/medpaf/anchor/releases/tag/linux"])

    def update_from_deb(self, pkexec_code=0, download_error=None):
        """Check for updates… → Update, with the download, password prompt and restart replaced."""
        self.open(self.ready_phone())
        self.wait_page("main")
        deb = Path(self.tmp.name, "anchor-linux.deb")
        with mock.patch.object(anchor.AnchorWindow, "can_update_itself", lambda win: True), \
                mock.patch.object(anchor.updates, "check", return_value=anchor.updates.AVAILABLE), \
                mock.patch.object(anchor.updates, "download", return_value=deb, side_effect=download_error) as download, \
                mock.patch.object(anchor.subprocess, "run",
                                  return_value=subprocess.CompletedProcess([], pkexec_code)) as run, \
                mock.patch.object(anchor.subprocess, "Popen") as popen, \
                mock.patch.object(Adw.Application, "quit") as quit_:
            self.win.activate_action("win.updates", None)
            self.pump(lambda: self.dialogs, what="update answer")
            self.assertIn("installs it over this one and restarts", self.dialogs[-1].get_body())
            self.dialogs[-1].emit("response", "update")
            self.pump(lambda: quit_.called or self.errors or any("Update" in t or "Password" in t for t in self.toasts[1:]),
                      what="update finished")
        return download, run, popen, quit_, deb

    def test_update_from_the_deb_installs_and_restarts(self):
        download, run, popen, quit_, deb = self.update_from_deb()
        download.assert_called_once_with("linux", "anchor-linux.deb")
        self.assertEqual(run.call_args[0][0], ["pkexec", "--disable-internal-agent", anchor.UPDATE_HELPER, str(deb)])
        self.assertIn("exec anchor", popen.call_args[0][0][-1], "the new version starts once this one closes")
        quit_.assert_called_once()
        self.assertTrue(os.path.isdir(os.path.join(self.tmp.name, "anchor")), "the key stays")

    def test_update_cancelled_at_the_password(self):
        _download, _run, popen, quit_, _deb = self.update_from_deb(pkexec_code=126)
        self.assertIn("Update cancelled", self.toasts)
        popen.assert_not_called()
        quit_.assert_not_called()

    def test_update_download_failing_is_explained(self):
        _download, run, _popen, quit_, _deb = self.update_from_deb(download_error=OSError("offline"))
        self.assertEqual(self.errors[-1][0], "Couldn't update Anchor")
        run.assert_not_called()  # nothing to install, so no password prompt
        quit_.assert_not_called()

    def test_only_the_deb_updates_itself(self):
        with mock.patch.object(anchor, "PACKAGED", False):
            self.open(self.ready_phone())
            self.assertFalse(self.win.can_update_itself(), "install.sh copies get the download page instead")

    def test_check_for_updates_not_now_opens_nothing(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.assertEqual(self.check_updates(anchor.updates.AVAILABLE, press="later"), [])

    def test_check_for_updates_on_a_copy_not_built_by_github(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        opened = self.check_updates(anchor.updates.UNKNOWN, press="download")
        self.assertEqual(self.dialogs[-1].get_heading(), "Can't tell which version this is")
        self.assertEqual(opened, ["https://github.com/medpaf/anchor/releases/tag/linux"])

    def test_check_for_updates_without_internet(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.check_updates(error=OSError("no network"))
        self.assertEqual(self.errors[-1][0], "Couldn't check for updates")

    def test_buy_me_a_coffee_opens_the_sponsors_page(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        opened = []
        with mock.patch.object(Gtk.UriLauncher, "launch", lambda l, *a: opened.append(l.get_uri())):
            self.win.activate_action("win.donate", None)
        self.assertEqual(opened, ["https://github.com/sponsors/medpaf"])

    def test_window_title_shows_the_version(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.assertEqual(self.win.get_title(), "Anchor - Free")
        self.assertEqual(self.win.title_widget.get_title(), "Anchor - Free")

    def test_about_shows_edition_and_developer(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        self.about_links = []
        with mock.patch.object(Adw.AboutDialog, "present", lambda d, parent: self.dialogs.append(d)), \
                mock.patch.object(Adw.AboutDialog, "add_link", lambda d, title, url: self.about_links.append((title, url))):
            self.win.activate_action("win.about", None)
        about = self.dialogs[-1]
        self.assertEqual(about.get_application_name(), "Anchor - Free")
        self.assertEqual((about.get_developer_name(), about.get_version()), ("", ""), "no name or version under the title")
        self.assertEqual(about.get_website(), "", "no built-in Website row")
        self.assertIn(("GitHub repository", "https://github.com/medpaf/anchor"), self.about_links)

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

    def uninstall_from_deb(self, pkexec_code):
        self.open(self.ready_phone())
        self.wait_page("main")
        key_dir = os.path.join(self.tmp.name, "anchor")
        self.assertTrue(os.path.isdir(key_dir))
        self.assertEqual(anchor.GLib.get_user_data_dir(), self.tmp.name, "only the test's own folder is touched")
        with mock.patch.object(anchor, "PACKAGED", True), \
                mock.patch.object(anchor.os, "access", return_value=True), \
                mock.patch.object(anchor.shutil, "which", return_value="/usr/bin/pkexec"), \
                mock.patch.object(anchor.subprocess, "run",
                                  return_value=subprocess.CompletedProcess([], pkexec_code)) as run, \
                mock.patch.object(Adw.Application, "quit"):
            self.win.on_uninstall_desktop()
            self.dialogs[-1].emit("response", "uninstall")
            self.pump(lambda: self.dialogs[-1].get_heading() == "Uninstalled", what="done")
        self.assertFalse(os.path.exists(key_dir), "the backup key is deleted")
        self.assertEqual(run.call_args[0][0], ["pkexec", "--disable-internal-agent", anchor.UNINSTALL_HELPER])
        return self.dialogs[-1].get_body()

    def test_uninstall_from_the_deb_removes_the_package(self):
        self.assertEqual(self.uninstall_from_deb(0), "Anchor has been removed from this computer.")

    def test_uninstall_from_the_deb_when_the_password_is_cancelled(self):
        self.assertIn("sudo apt remove anchor", self.uninstall_from_deb(126))

    def test_menus_are_square_only_on_x11(self):
        # GTK 4 can't draw a menu's corners see-through on X11, so menus are square there.
        X11Display = type("X11Display", (), {})
        WaylandDisplay = type("WaylandDisplay", (), {})
        self.assertTrue(anchor.is_x11(X11Display()))
        self.assertFalse(anchor.is_x11(WaylandDisplay()))
        self.assertIn("popover > contents { border-radius: 0; }", anchor.X11_CSS)

    def test_uninstall_of_an_install_sh_copy_deletes_the_key_too(self):
        self.open(self.ready_phone())
        self.wait_page("main")
        key_dir = os.path.join(self.tmp.name, "anchor")
        self.assertTrue(os.path.isdir(key_dir))
        self.assertEqual(anchor.GLib.get_user_data_dir(), self.tmp.name, "only the test's own folder is touched")
        with mock.patch.object(anchor, "PACKAGED", False), \
                mock.patch.object(anchor.shutil, "which", return_value=None), \
                mock.patch.object(anchor.subprocess, "run") as run, \
                mock.patch.object(Adw.Application, "quit"):
            self.win.on_uninstall_desktop()
            self.assertIn("its launcher and your backup key from this computer", self.dialogs[-1].get_body())
            self.dialogs[-1].emit("response", "uninstall")
            self.pump(lambda: self.dialogs[-1].get_heading() == "Uninstalled", what="done")
        self.assertFalse(os.path.exists(key_dir), "the backup key is deleted")
        run.assert_not_called()

    def test_a_new_message_replaces_the_one_on_screen(self):
        win = mock.Mock(spec=[])
        win.toasts = mock.Mock()
        with mock.patch.object(anchor.Adw, "Toast") as toast:
            toast.new.side_effect = lambda text: mock.Mock(name=text)
            REAL_TOAST(win, "Instagram released")
            first = win.current_toast
            REAL_TOAST(win, "TikTok released")
        first.dismiss.assert_called_once()
        self.assertEqual(win.toasts.add_toast.call_count, 2)

    def test_uninstall_desktop_asks_first(self):
        phone = self.ready_phone()
        self.open(phone)
        self.wait_page("main")
        self.win.on_uninstall_desktop()
        self.assertIn("Uninstall Anchor from this computer?", self.dialogs[-1].get_heading())
        # Cancelling must not touch the phone or the app.
        self.dialogs[-1].emit("response", "cancel")
        self.assertTrue(phone.installed)
        self.wait_page("main")


if __name__ == "__main__":
    unittest.main()
