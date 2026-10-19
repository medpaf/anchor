#!/usr/bin/env python3
"""Anchor: block apps on your Android phone; only this computer can unblock them."""

import json
import os
import subprocess
import shutil
from datetime import datetime
import sys
import threading
import time
import uuid
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adbclient as ac  # noqa: E402
import catalog  # noqa: E402
import updates  # noqa: E402
from permnames import friendly  # noqa: E402
from timetext import DAY_NAMES, clock, countdown, days_text, hours_text, plural  # noqa: E402

APP_ID = "app.anchor.Desktop"
APK = HERE / "anchor-agent.apk"
PACKAGED = str(HERE).startswith("/usr/")  # installed from anchor-linux.deb, not by install.sh
VERSION = "1.0"
WINDOW_TITLE = "Anchor - Free"
WEBSITE = "https://github.com/medpaf/anchor"
UPDATE_CHANNEL = "linux"  # Menu → Check for updates… compares with the "linux" release
DONATE_URL = "https://github.com/sponsors/medpaf"  # free version: Menu → Buy me a coffee

CSS = """
/* ---- Palette: deep violet-black with a violet accent ---- */
@define-color accent_color #B39DFF;
@define-color accent_bg_color #7C3AED;
@define-color accent_fg_color #FFFFFF;
@define-color window_bg_color #0D0A14;
@define-color window_fg_color #EEEAF7;
@define-color view_bg_color #0D0A14;
@define-color view_fg_color #EEEAF7;
@define-color headerbar_bg_color #0D0A14;
@define-color headerbar_fg_color #EEEAF7;
@define-color headerbar_border_color transparent;
@define-color headerbar_backdrop_color #0D0A14;
@define-color card_bg_color #16121F;
@define-color card_fg_color #EEEAF7;
@define-color dialog_bg_color #1A1525;
@define-color dialog_fg_color #EEEAF7;
@define-color popover_bg_color #1E1829;
@define-color popover_fg_color #EEEAF7;
@define-color success_color #6EE7B7;
@define-color warning_color #FCD34D;
@define-color error_color #FCA5A5;
@define-color destructive_color #FCA5A5;

window, .background { background-color: @window_bg_color; }
headerbar { background: transparent; box-shadow: none; }
headerbar .title { font-weight: 800; letter-spacing: 0.3px; }
headerbar .subtitle { color: alpha(@window_fg_color, 0.5); }
.dim-label { color: alpha(@window_fg_color, 0.58); opacity: 1; }

/* ---- Status bar ---- */
.hero {
  padding: 18px 20px;
  border-radius: 18px;
  background-color: #16121F;
  box-shadow: 0 0 0 1px alpha(white, 0.06);
}
.hero.anchored { background-color: #1B1529; box-shadow: 0 0 0 1px alpha(#8B5CF6, 0.28); }
.hero-title { font-size: 1.38em; font-weight: 800; }
.hero-subtitle { color: alpha(@window_fg_color, 0.6); font-size: 0.93em; }

/* ---- Buttons ---- */
.cta {
  padding: 9px 30px; border-radius: 999px;
  font-size: 1.02em; font-weight: 800; letter-spacing: 0.2px;
  color: white;
  background-image: linear-gradient(135deg, #9B6DFF, #6D28D9);
  box-shadow: none;
  border: none;
}
.setup-cta { padding: 12px 48px; font-size: 1.1em; }
.cta:hover { background-image: linear-gradient(135deg, #AA82FF, #7C3AED); }
.cta:active { background-image: linear-gradient(135deg, #8B5CF6, #5B21B6); }
.cta:disabled { background-image: none; background-color: alpha(white, 0.06);
                color: alpha(white, 0.32); box-shadow: none; }
.cta.release {
  background-image: none; background-color: alpha(white, 0.04);
  color: #E4DBFF; box-shadow: inset 0 0 0 1px alpha(#A78BFA, 0.65);
}
.cta.release:hover { background-color: alpha(#8B5CF6, 0.16); }
.link-button { color: #C4B5FD; font-weight: 700; font-size: 0.9em; border-radius: 999px;
               padding: 3px 12px; min-height: 0; }
.link-button:hover { background-color: alpha(#8B5CF6, 0.14); }

/* ---- Search, sections and lists ---- */
entry.search, searchentry {
  min-height: 42px; border-radius: 14px; padding-left: 12px;
  background-color: #16121F; box-shadow: inset 0 0 0 1px alpha(white, 0.06);
}
searchentry:focus-within { box-shadow: inset 0 0 0 2px alpha(#8B5CF6, 0.8); }
.section-title { font-size: 1.08em; font-weight: 800; }
.section-icon { color: #C4B5FD; }
list.boxed-list.folded > row:first-child { border-bottom-color: transparent;
                                           border-bottom-left-radius: 18px; border-bottom-right-radius: 18px; }
.section-hint { color: alpha(@window_fg_color, 0.5); }
list.boxed-list {
  background-color: #16121F; border-radius: 18px;
  box-shadow: 0 0 0 1px alpha(white, 0.06), 0 6px 18px alpha(black, 0.3);
}
list.boxed-list > row { border-color: alpha(white, 0.05); }
list.boxed-list > row:hover { background-color: alpha(#8B5CF6, 0.07); }
list.boxed-list > row:first-child { border-top-left-radius: 18px; border-top-right-radius: 18px; }
list.boxed-list > row:last-child { border-bottom-left-radius: 18px; border-bottom-right-radius: 18px; }
row .subtitle { color: alpha(@window_fg_color, 0.5); }
.app-icon { border-radius: 12px; }
.sched-button { color: alpha(@window_fg_color, 0.45); border-radius: 999px; }
.sched-button.accent { color: #B39DFF; background-color: alpha(#8B5CF6, 0.16); }
switch { background-color: alpha(white, 0.12); }
switch:checked { background-color: #7C3AED; }
switch slider { background-color: #F4F0FF; }

.pill-small { border-radius: 999px; padding: 4px 14px; font-weight: 700; font-size: 0.9em;
              color: #E4DBFF; background-color: alpha(white, 0.04);
              box-shadow: inset 0 0 0 1px alpha(#A78BFA, 0.55); }
.pill-small:hover { background-color: alpha(#8B5CF6, 0.16); }
.never-allow image { color: #C4B5FD; }
.row-anchor { border-radius: 999px; padding: 5px 16px; font-weight: 800; font-size: 0.92em; color: white;
              background-image: linear-gradient(135deg, #9B6DFF, #6D28D9); border: none;
              box-shadow: none; min-width: 64px; }
.row-anchor:hover { background-image: linear-gradient(135deg, #AA82FF, #7C3AED); }
.row-anchor.release { background-image: none; background-color: alpha(white, 0.04); color: #E4DBFF;
                      box-shadow: inset 0 0 0 1px alpha(#A78BFA, 0.65); }
.row-anchor.release:hover { background-color: alpha(#8B5CF6, 0.16); }
.row-uninstall { border-radius: 999px; padding: 5px 12px; font-weight: 700; font-size: 0.88em;
                 background: none; box-shadow: none; color: alpha(@window_fg_color, 0.45); }
.row-uninstall:hover { color: #FCA5A5; background-color: alpha(#F87171, 0.12); }
.pill-small.danger { color: #FECACA; box-shadow: inset 0 0 0 1px alpha(#F87171, 0.6); }
.pill-small.danger:hover { background-color: alpha(#F87171, 0.14); }

/* ---- Dialogs, popovers, toasts ---- */
dialog.alert .heading, .alert .heading { font-weight: 800; }
/* Only a thin outline: a soft outer shadow turns into a black box around the menu on X11. */
popover > contents { border-radius: 14px; box-shadow: 0 0 0 1px alpha(white, 0.08); }
toast { background-color: #241C33; color: #F1ECFF; border-radius: 999px;
        box-shadow: 0 0 0 1px alpha(#8B5CF6, 0.35), 0 10px 30px alpha(black, 0.5); }

/* ---- Setup and misc ---- */
.step-number { min-width: 28px; min-height: 28px; border-radius: 99px;
               background-color: alpha(#8B5CF6, 0.2); color: #C4B5FD; font-weight: 800; }
.day-toggle { min-width: 42px; padding-left: 4px; padding-right: 4px; font-weight: 700; }
.day-toggle:checked { background-image: linear-gradient(135deg, #9B6DFF, #6D28D9); color: white; }
.time-spin { font-size: 1.4em; font-weight: 800; }
.key-label { font-family: monospace; font-size: 1.3em; letter-spacing: 1px; padding: 14px;
             border-radius: 14px; background-color: alpha(#8B5CF6, 0.12); color: #E4DBFF; }
statuspage > scrolledwindow > viewport > box > .title { font-weight: 800; }
statuspage > scrolledwindow > viewport > box { margin-left: 24px; margin-right: 24px; }
.status-text { line-height: 1.3; color: alpha(@window_fg_color, 0.75); }
"""


RUNNING = set()  # background threads still at work (tests wait for these between cases)


def in_background(work, done=None, fail=None):
    """Runs work() on a thread, then done(result) or fail(exception) on the GTK main loop."""

    def runner():
        try:
            result = work()
        except Exception as e:  # noqa: BLE001 - shown to the user
            # Bind e now: Python clears the name when the except block ends.
            if fail:
                GLib.idle_add(lambda err=e: fail(err) and False)
            return
        if done:
            GLib.idle_add(lambda: done(result) and False)

    thread = threading.Thread(target=lambda: (runner(), RUNNING.discard(thread)), daemon=True)
    RUNNING.add(thread)
    thread.start()


RELEASE_CHECK = "/usr/libexec/anchor-release-check"  # installed with polkit/app.anchor.release.policy
RELEASE_POLICY = "/usr/share/polkit-1/actions/app.anchor.release.policy"
UNINSTALL_HELPER = "/usr/libexec/anchor-uninstall"  # removes the .deb, or install.sh's system files
UPDATE_HELPER = "/usr/libexec/anchor-update"  # installs a downloaded anchor-linux.deb (only in the .deb)


def system_password_check():
    """Asks for the computer's admin password with the system's own dialog (polkit). Anchor never
    sees the password; it only learns whether it was accepted. Returns "ok", "cancelled", "denied"
    or "missing". With Anchor's polkit policy installed the dialog says "Authentication is required
    to release your anchored apps"; without it, polkit's generic "...to run `/bin/true`..."."""
    if not shutil.which("pkexec"):
        return "missing"
    command = RELEASE_CHECK if os.access(RELEASE_CHECK, os.X_OK) else "/bin/true"
    try:
        code = subprocess.run(["pkexec", "--disable-internal-agent", command],
                              capture_output=True, timeout=300).returncode
    except subprocess.TimeoutExpired:
        return "cancelled"
    return {0: "ok", 126: "cancelled"}.get(code, "denied")


class PhoneLimit(Exception):
    """Free version: this computer is already set up for a different phone."""

    def __init__(self, other):
        super().__init__("This computer is set up for another phone")
        self.other = other


class _HeaderText:
    """Lets a section's title or hint be set like a label, while living on its header row."""

    def __init__(self, row, section, part):
        self.row, self.section, self.part = row, section, part

    def set_label(self, text):
        (self.row.set_title if self.part == "title" else self.row.set_subtitle)(text)

    def get_label(self):
        return self.row.get_title() if self.part == "title" else self.row.get_subtitle()


class AnchorWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=WINDOW_TITLE, default_width=580, default_height=780)
        self.set_size_request(360, 480)
        adb_path = ac.find_adb()
        self.adb = ac.Adb(adb_path) if adb_path else None
        self.keys = ac.KeyStore()
        self.device_key = None
        self.agent = None
        self.model = ""
        self.device_id = None  # the connected phone's Android ID
        self.status = {}
        self.selected = set()
        self.rows = {}
        self.polling = False
        self.working = False
        self.sync_source = None
        self.populating = False
        self.schedules = []
        self.app_dialog = None
        self.details = None
        self.icons = {}
        self.install_blocks = []
        self.never_key = None
        self.placing = False
        self.placeholder_failed = {}  # pkg -> why the placeholder couldn't be installed

        self.build_ui()
        self.install_actions()
        if self.adb:
            self.show_page("nophone")
            GLib.timeout_add_seconds(2, self.poll)
            self.poll()
        else:
            self.show_page("noadb")

    # ---- UI construction ---------------------------------------------------------------

    def build_ui(self):
        self.toasts = Adw.ToastOverlay()
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.title_widget = Adw.WindowTitle(title=WINDOW_TITLE, subtitle="")
        header.set_title_widget(self.title_widget)

        menu = Gio.Menu()
        section = Gio.Menu()
        section.append("Refresh", "win.refresh")
        section.append("Backup key…", "win.backup")
        section.append("Use a backup key…", "win.import")
        menu.append_section(None, section)
        danger = Gio.Menu()
        danger.append("Remove Anchor from phone…", "win.remove")
        danger.append("Uninstall Anchor from this computer…", "win.uninstall")
        menu.append_section(None, danger)
        about = Gio.Menu()
        about.append("Check for updates…", "win.updates")
        about.append("Buy me a coffee…", "win.donate")
        about.append("About Anchor", "win.about")
        menu.append_section(None, about)
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu, tooltip_text="Menu")
        header.pack_end(menu_button)
        view.add_top_bar(header)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=180)
        self.stack.add_named(self.build_simple_page(
            "dialog-warning-symbolic", "adb is missing",
            "Anchor uses adb to talk to your phone. Install it, then reopen Anchor:\n\n"
            "<tt>sudo apt install adb</tt>"), "noadb")
        self.stack.add_named(self.build_simple_page(
            "phone-symbolic", "Connect your phone",
            "Plug your Android phone into this computer with a USB cable.\n\n"
            "First time? Turn on USB debugging: open <b>Settings → About phone</b>, tap "
            "<b>Build number</b> seven times, then go to <b>Settings → System → Developer options</b> "
            "and switch on <b>USB debugging</b>.", spinner=True), "nophone")
        self.stack.add_named(self.build_simple_page(
            "dialog-password-symbolic", "Allow this computer",
            "Unlock your phone and tap <b>Allow</b> on the “Allow USB debugging?” prompt. "
            "Tick <b>Always allow from this computer</b> so you don't have to do it again.\n\n"
            "No prompt? Unplug the cable and plug it back in.", spinner=True), "unauthorized")
        self.stack.add_named(self.build_simple_page(
            None, "Checking your phone…", "", spinner=True), "loading")
        self.stack.add_named(self.build_foreign_page(), "foreign")
        self.stack.add_named(self.build_limit_page(), "limit")
        self.stack.add_named(self.build_setup_page(), "setup")
        self.stack.add_named(self.build_main_page(), "main")

        view.set_content(self.stack)
        self.toasts.set_child(view)
        self.set_content(self.toasts)

    def build_simple_page(self, icon, title, markup, spinner=False):
        page = Adw.StatusPage(title=title)
        if icon:
            page.set_icon_name(icon)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24, margin_start=32, margin_end=32)
        if markup:
            label = Gtk.Label(use_markup=True, wrap=True, justify=Gtk.Justification.CENTER, max_width_chars=44)
            label.add_css_class("status-text")
            label.set_markup(markup)
            box.append(label)
        if spinner:
            sp = Gtk.Spinner(spinning=True, halign=Gtk.Align.CENTER)
            sp.set_size_request(24, 24)
            box.append(sp)
        page.set_child(box)
        return page

    def build_foreign_page(self):
        page = Adw.StatusPage(
            icon_name="changes-prevent-symbolic", title="Anchored to another computer",
            description="This phone was set up with a different computer. To control it from here, "
                        "enter that computer's backup key.")
        button = Gtk.Button(label="Enter backup key", halign=Gtk.Align.CENTER)
        button.add_css_class("cta")
        button.connect("clicked", lambda *_: self.on_import())
        page.set_child(button)
        return page

    def build_limit_page(self):
        # Free version: one phone per computer. Shown for a phone paired with this key that isn't that one.
        self.limit_page = Adw.StatusPage(icon_name="phone-symbolic", title="The free version works with one phone")
        button = Gtk.Button(label="Remove Anchor from this phone", halign=Gtk.Align.CENTER)
        button.add_css_class("cta")
        button.connect("clicked", lambda *_: self.on_remove())
        self.limit_page.set_child(button)
        return self.limit_page

    def limit_text(self, other):
        return (f"This computer is set up for {other.get('model') or 'another phone'}. To use Anchor with "
                f"{self.model}, connect that phone and remove Anchor from it first, or get Anchor Pro "
                "to use more phones.")

    def build_setup_page(self):
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(maximum_size=560, margin_top=24, margin_bottom=32, margin_start=16, margin_end=16)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)

        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        top.append(Gtk.Image(icon_name="app.anchor.Desktop", pixel_size=96))
        title = Gtk.Label(label="Set up your phone")
        title.add_css_class("title-1")
        top.append(title)
        intro = Gtk.Label(
            label="Anchor needs a small companion app on your phone. It becomes the phone's "
                  "device owner, which lets it block apps in a way the phone itself can't undo.",
            wrap=True, justify=Gtk.Justification.CENTER, max_width_chars=52)
        intro.add_css_class("dim-label")
        top.append(intro)
        box.append(top)

        before = Adw.PreferencesGroup(title="Before you start")
        acc = Adw.ActionRow(
            title="Remove all accounts from the phone for a moment",
            subtitle="Settings → Passwords &amp; accounts. Android only allows a device owner on a phone "
                     "with no accounts. Add them back right after setup.")
        acc.set_subtitle_lines(0)
        acc.add_prefix(Gtk.Image(icon_name="avatar-default-symbolic"))
        before.add(acc)
        users = Adw.ActionRow(
            title="Remove extra users and work profiles",
            subtitle="Guest users, work profiles, “Second space” or “Dual apps” must go too.")
        users.set_subtitle_lines(0)
        users.add_prefix(Gtk.Image(icon_name="system-users-symbolic"))
        before.add(users)
        box.append(before)

        steps = Adw.PreferencesGroup(title="Steps")
        self.step_rows = []
        for i, (title, subtitle) in enumerate([
            ("Install Anchor on the phone", "Copies the companion app over USB"),
            ("Make Anchor the device owner", "Lets Anchor block apps at the system level"),
            ("Pair with this computer", "From now on only this computer can release your apps"),
        ]):
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            number = Gtk.Label(label=str(i + 1), valign=Gtk.Align.CENTER)
            number.add_css_class("step-number")
            row.add_prefix(number)
            state = Gtk.Stack(valign=Gtk.Align.CENTER)
            state.add_named(Gtk.Box(), "todo")
            state.add_named(Gtk.Spinner(spinning=True), "working")
            done = Gtk.Image(icon_name="object-select-symbolic")
            done.add_css_class("success")
            state.add_named(done, "done")
            row.add_suffix(state)
            steps.add(row)
            self.step_rows.append(state)
        box.append(steps)

        self.setup_button = Gtk.Button(label="Set up phone", halign=Gtk.Align.CENTER)
        self.setup_button.add_css_class("cta")
        self.setup_button.add_css_class("setup-cta")
        self.setup_button.connect("clicked", self.on_setup)
        box.append(self.setup_button)

        clamp.set_child(box)
        scroller.set_child(clamp)
        return scroller

    def build_main_page(self):
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(maximum_size=600, margin_top=18, margin_bottom=32, margin_start=16, margin_end=16)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)

        # Status bar: emblem, what's going on, and the one main button.
        self.hero = Gtk.Box(spacing=16)
        self.hero.add_css_class("card")
        self.hero.add_css_class("hero")
        self.hero_icon = Gtk.Image(pixel_size=60, valign=Gtk.Align.CENTER)
        self.hero.append(self.hero_icon)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, hexpand=True, valign=Gtk.Align.CENTER)
        self.hero_title = Gtk.Label(xalign=0)
        self.hero_title.add_css_class("hero-title")
        text.append(self.hero_title)
        self.hero_subtitle = Gtk.Label(wrap=True, xalign=0, max_width_chars=38)
        self.hero_subtitle.add_css_class("hero-subtitle")
        text.append(self.hero_subtitle)
        self.hero.append(text)

        actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
        self.hero_button = Gtk.Button(halign=Gtk.Align.CENTER)
        self.hero_button.add_css_class("cta")
        self.hero_button.connect("clicked", self.on_hero_clicked)
        actions.append(self.hero_button)
        self.pause_button = Gtk.Button(label="Bring back now", halign=Gtk.Align.CENTER,
                                       tooltip_text="Bring scheduled apps back now")
        self.pause_button.add_css_class("flat")
        self.pause_button.add_css_class("link-button")
        self.pause_button.connect("clicked", lambda *_: self.run_shift(None, unshift=True))
        actions.append(self.pause_button)
        self.hero.append(actions)
        box.append(self.hero)

        self.search = Gtk.SearchEntry(placeholder_text="Search your apps")
        self.search.connect("search-changed", self.on_search_changed)
        box.append(self.search)

        self.build_never_allow(box)

        # Two sections: the apps on your block list, and everything else. Switching an app on or
        # off moves it from one to the other.
        self.picked_title, self.picked_hint, self.picked_list = self.build_section(
            box, "Nothing anchored. Tap Anchor on an app below.", "anchor-section")
        self.other_title, self.other_hint, self.other_list = self.build_section(
            box, "No other apps", "view-app-grid-symbolic")

        clamp.set_child(box)
        scroller.set_child(clamp)
        return scroller

    def build_never_allow(self, parent):
        rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        rows.add_css_class("boxed-list")
        self.never_row = Adw.ExpanderRow(title="Never allow")
        never_icon = Gtk.Image(icon_name="never-allow-section")  # the phone app's ic_block, same size and colour
        never_icon.add_css_class("section-icon")
        self.never_row.add_prefix(never_icon)
        self.never_row.add_css_class("never-allow")
        rows.append(self.never_row)
        self.never_children = []
        parent.append(rows)

    def update_never_allow(self):
        st = self.status
        blocks = st.get("install_blocks", [])
        kept, caught = set(st.get("install_kept", [])), set(st.get("install_caught", []))
        placeholders, missing = set(st.get("install_placeholders", [])), set(st.get("install_missing", []))
        key = json.dumps([blocks, sorted(kept), sorted(caught), sorted(placeholders), sorted(missing),
                          sorted(self.placeholder_failed), self.placing, sorted(self.icons)])
        if key == self.never_key:
            return
        self.never_key = key
        self.install_blocks = blocks
        n = len(blocks)
        self.never_row.set_title(f"Never allow ({n})")
        self.never_row.set_subtitle("Apps that can't be installed.")
        for child in self.never_children:
            self.never_row.remove(child)
        self.never_children = []
        for app in sorted(blocks, key=lambda a: a["name"].casefold()):
            pkg = app["pkg"]
            row = Adw.ActionRow(title=app["name"])
            row.set_use_markup(False)
            uninstall = None
            if pkg in caught:
                row.set_subtitle("Installed before the block was set up, so it's hidden. "
                                 "Uninstall it to stop it from being installed again.")
                uninstall = Gtk.Button(label="Uninstall", valign=Gtk.Align.CENTER,
                                       tooltip_text=f"Uninstall {app['name']} from your phone")
                uninstall.add_css_class("pill-small")
                uninstall.add_css_class("danger")
                uninstall.connect("clicked", lambda _b, a=app: self.on_uninstall_blocked(a))
            elif pkg in kept:
                row.set_subtitle("Was already on your phone, so it's not affected. Anchor it to hide it.")
            elif pkg in placeholders:
                row.set_subtitle(pkg)  # blocked from being installed: show which package
            elif pkg in self.placeholder_failed:
                row.set_subtitle("Can be installed, but is hidden right away (the install couldn't be blocked)")
            else:
                row.set_subtitle("Blocking the install…" if self.placing else "Can't be used if installed")
            row.set_subtitle_lines(2)
            release = Gtk.Button(label="Release", valign=Gtk.Align.CENTER,
                                 tooltip_text=f"Remove {app['name']} from Never allow")
            release.add_css_class("pill-small")
            release.connect("clicked", lambda _b, p=pkg: self.release_install_block(p))
            if uninstall:
                row.add_suffix(uninstall)
            row.add_suffix(release)
            row.pkg, row.release, row.uninstall = pkg, release, uninstall
            self.never_row.add_row(row)
            self.never_children.append(row)
        add = Adw.ActionRow(title="Add an app…", activatable=True)
        add.add_prefix(Gtk.Image(icon_name="list-add-symbolic"))
        add.connect("activated", lambda *_: self.on_add_install_block())
        self.never_row.add_row(add)
        self.never_children.append(add)

    def ensure_placeholders(self):
        """Installs a placeholder for every never-allowed app that isn't on the phone, so the real
        app can't be installed."""
        missing = [p for p in self.status.get("install_missing", []) if p not in self.placeholder_failed]
        if not missing or self.placing or not self.agent:
            return
        agent, token = self.agent, self.keys.token
        self.placing = True
        self.update_never_allow()

        def work():
            failed = {}
            for pkg in missing:
                try:
                    agent.install_placeholder(pkg)
                except Exception as e:  # noqa: BLE001 - shown on the row
                    failed[pkg] = str(e)
            return failed, agent.status(token)

        def done(result):
            failed, st = result
            self.placing = False
            self.placeholder_failed.update(failed)
            self.apply_status(st)
            blocked = len(missing) - len(failed)
            if blocked:
                self.toast(f"{plural(blocked, 'app')} can't be installed on your phone now")

        def fail(e):
            self.placing = False
            self.update_never_allow()

        in_background(work, done, fail)

    def on_uninstall_blocked(self, app):
        d = Adw.AlertDialog.new(
            f"Uninstall {app['name']}?",
            f"{app['name']} and its data are removed from your phone. Anchor then stops it from being "
            "installed again, until you release it here.")
        d.add_response("cancel", "Cancel")
        d.add_response("uninstall", "Uninstall")
        d.set_response_appearance("uninstall", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_close_response("cancel")

        def response(_d, rid):
            if rid != "uninstall":
                return
            agent, token, pkg = self.agent, self.keys.token, app["pkg"]
            self.working = True

            def work():
                agent.uninstall_blocked(token, pkg)
                for _ in range(40):  # the phone uninstalls in the background
                    st = agent.status(token)
                    if pkg in st.get("install_missing", []):
                        return st
                    time.sleep(0.25)
                return agent.status(token)

            def done(st):
                self.working = False
                self.apply_status(st)
                self.toast(f"{app['name']} uninstalled")
                self.ensure_placeholders()

            def fail(e):
                self.working = False
                self.error_dialog(f"Couldn't uninstall {app['name']}", str(e))

            in_background(work, done, fail)

        d.connect("response", response)
        d.present(self)

    def save_install_blocks(self, apps, message, reload=False):
        agent, token = self.agent, self.keys.token
        self.working = True

        def done(st):
            self.working = False
            self.apply_status(st)
            if message:
                self.toast(message)
            if reload:
                self.reload_apps()
            self.ensure_placeholders()

        def fail(e):
            self.working = False
            self.error_dialog("Couldn't update Never allow", str(e))

        in_background(lambda: agent.set_install_blocks(token, apps), done, fail)

    def release_install_block(self, pkg):
        app = next(a for a in self.install_blocks if a["pkg"] == pkg)
        was_hidden = pkg in self.status.get("install_caught", [])
        self.save_install_blocks([a for a in self.install_blocks if a["pkg"] != pkg],
                                 f"{app['name']} released: it can be installed and used again", reload=was_hidden)

    def add_install_blocks(self, apps):
        have = {a["pkg"] for a in self.install_blocks}
        new = [a for a in apps if a["pkg"] not in have]
        if not new:
            self.toast("Already on your 'Never allow' list")
            return
        names = new[0]["name"] if len(new) == 1 else plural(len(new), "app")
        for a in new:
            self.placeholder_failed.pop(a["pkg"], None)
        on_phone = [a for a in new if self.uninstalls_when_never_allowed(a["pkg"])]
        if on_phone:
            self.confirm_never_allow_uninstall(new, on_phone)
            return
        self.save_install_blocks(self.install_blocks + new, f"{names} added to Never allow")

    def uninstalls_when_never_allowed(self, pkg):
        """On the phone, installed by the user and not anchored: adding it to Never allow uninstalls it."""
        row = self.rows.get(pkg)
        return bool(row and row.uninstall_button and pkg not in self.selected)

    def confirm_never_allow_uninstall(self, new, on_phone):
        """Asks before uninstalling apps that are on the phone, then uninstalls them and adds them all."""
        one = len(on_phone) == 1
        names = on_phone[0]["name"] if one else (", ".join(a["name"] for a in on_phone[:-1])
                                                 + " and " + on_phone[-1]["name"])
        it, its = ("it", "its") if one else ("them", "their")
        d = Adw.AlertDialog.new(f"Uninstall {names}?",
                                f"{names} {'is' if one else 'are'} on your phone. Adding {it} to Never allow "
                                f"uninstalls {it}, with {its} data, and stops {it} from being installed again "
                                f"until you release {it} here.")
        d.add_response("cancel", "Cancel")
        d.add_response("uninstall", "Uninstall")
        d.set_response_appearance("uninstall", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_close_response("cancel")

        def response(_d, rid):
            if rid != "uninstall":
                return
            agent, token, blocks = self.agent, self.keys.token, self.install_blocks + new
            self.working = True

            def work():
                for a in on_phone:
                    agent.uninstall_app(token, a["pkg"])
                for _ in range(40):  # the phone uninstalls in the background
                    if not any(agent.installed_package(a["pkg"]) for a in on_phone):
                        break
                    time.sleep(0.25)
                return agent.set_install_blocks(token, blocks)

            def done(st):
                self.working = False
                self.apply_status(st)
                self.toast(f"{names} uninstalled and added to Never allow")
                self.reload_apps()
                self.ensure_placeholders()

            def fail(e):
                self.working = False
                self.error_dialog(f"Couldn't uninstall {names}", str(e))
                self.reload_apps()

            in_background(work, done, fail)

        d.connect("response", response)
        d.present(self)

    def on_add_install_block(self):
        d = Adw.AlertDialog.new("Never allow an app",
                                "It can't be used on your phone, even if you install it, until you release "
                                "it here. If it's on your phone, Anchor asks before uninstalling it.")
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        entry = Gtk.Entry(placeholder_text="Play Store link or package name", activates_default=True)
        content.append(entry)
        have = {a["pkg"] for a in self.install_blocks}
        options = [(p, n) for p, n in catalog.SOCIAL + catalog.SUGGESTIONS if p not in have]
        if options:
            label = Gtk.Label(label="Suggestions", xalign=0)
            label.add_css_class("caption-heading")
            content.append(label)
            suggestions = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
            suggestions.add_css_class("boxed-list")
            for pkg, name in options:
                row = Adw.ActionRow(title=name, subtitle=pkg)
                add = Gtk.Button(icon_name="list-add-symbolic", valign=Gtk.Align.CENTER, tooltip_text=f"Add {name}")
                add.add_css_class("flat")
                add.connect("clicked", lambda _b, p=pkg, n=name: (self.add_install_blocks([{"pkg": p, "name": n}]),
                                                                   d.close()))
                row.add_suffix(add)
                row.set_activatable_widget(add)
                suggestions.append(row)
            scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, max_content_height=260,
                                          propagate_natural_height=True)
            scroller.set_child(suggestions)
            content.append(scroller)
        d.set_extra_child(content)
        d.add_response("cancel", "Cancel")
        d.add_response("add", "Add")
        d.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)
        d.set_default_response("add")
        d.set_close_response("cancel")
        d.entry = entry

        def response(_d, rid):
            if rid != "add" or not entry.get_text().strip():
                return
            try:
                pkg = catalog.parse_app(entry.get_text())
            except ValueError as e:
                self.error_dialog("That doesn't look like an app", str(e))
                return
            labels = {r.pkg: r.label for r in self.rows.values()}
            self.add_install_blocks([{"pkg": pkg, "name": catalog.name_for(pkg, labels)}])

        d.connect("response", response)
        d.present(self)

    def build_section(self, parent, empty_text, icon):
        """A card like Never allow: a header row (icon, title, hint, chevron) with the apps below it.
        Clicking the header folds the apps away."""
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        rows.add_css_class("boxed-list")
        rows.set_filter_func(self.filter_row)
        rows.set_sort_func(lambda a, b: (a.sort_key > b.sort_key) - (a.sort_key < b.sort_key))
        placeholder = Gtk.Label(label=empty_text, margin_top=18, margin_bottom=18)
        placeholder.add_css_class("dim-label")
        rows.set_placeholder(placeholder)
        rows.placeholder_label, rows.empty_text = placeholder, empty_text

        header = Adw.ActionRow(activatable=True)
        header.set_use_markup(False)
        image = Gtk.Image(icon_name=icon)
        image.add_css_class("section-icon")
        header.add_prefix(image)
        # Same as Never allow (an Adw.ExpanderRow): down while open, up while folded.
        chevron = Gtk.Image(icon_name="pan-down-symbolic")
        chevron.add_css_class("dim-label")
        header.add_suffix(chevron)
        header.is_header, header.sort_key = True, ""  # always first, never filtered out
        rows.append(header)
        rows.is_open = True

        def set_open(is_open):
            rows.is_open = is_open
            # Folded: the header is the whole card, so drop its separator and round its bottom.
            (rows.remove_css_class if is_open else rows.add_css_class)("folded")
            chevron.set_from_icon_name("pan-down-symbolic" if is_open else "pan-up-symbolic")
            rows.invalidate_filter()

        header.connect("activated", lambda *_: set_open(not rows.is_open))
        rows.set_open, rows.header = set_open, header
        section.append(rows)
        parent.append(section)
        return _HeaderText(header, section, "title"), _HeaderText(header, section, "subtitle"), rows

    def install_actions(self):
        for name, handler in [
            ("refresh", lambda *_: self.reprobe()),
            ("backup", lambda *_: self.on_backup()),
            ("import", lambda *_: self.on_import()),
            ("remove", lambda *_: self.on_remove()),
            ("uninstall", lambda *_: self.on_uninstall_desktop()),
            ("updates", lambda *_: self.on_check_updates()),
            ("donate", lambda *_: self.on_donate()),
            ("about", lambda *_: self.on_about()),
        ]:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)

    # ---- Navigation ------------------------------------------------------------------

    def show_page(self, name):
        self.stack.set_visible_child_name(name)
        self.lookup_action("remove").set_enabled(name in ("main", "setup", "foreign", "limit") and self.agent is not None)

    def toast(self, text, timeout=3):
        t = Adw.Toast.new(text)
        t.set_timeout(timeout)
        self.toasts.add_toast(t)

    def error_dialog(self, title, body, details=""):
        d = Adw.AlertDialog.new(title, body)
        if details:
            # Raw adb output can be a long Java stack trace: wrap it anywhere and scroll it, so it
            # never stretches the dialog past the window.
            expander = Gtk.Expander(label="Details")
            text = Gtk.Label(label=details, selectable=True, wrap=True, xalign=0, yalign=0,
                             wrap_mode=Pango.WrapMode.WORD_CHAR, max_width_chars=1, hexpand=True)
            text.add_css_class("monospace")
            text.add_css_class("caption")
            scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                          min_content_height=120, max_content_height=220,
                                          propagate_natural_height=True)
            scroller.set_child(text)
            expander.set_child(scroller)
            d.set_extra_child(expander)
        d.add_response("close", "OK")
        d.present(self)

    # ---- Device polling ----------------------------------------------------------------

    def poll(self):
        if self.polling:
            return True
        self.polling = True

        def done(devices):
            self.polling = False
            dev = next((d for d in devices if d.state == "device"), devices[0] if devices else None)
            key = (dev.serial, dev.state) if dev else None
            if key != self.device_key:
                self.device_key = key
                self.on_device_changed(dev)
            elif self.stack.get_visible_child_name() == "main" and not self.working:
                self.refresh_status()

        def fail(_e):
            self.polling = False

        in_background(self.adb.devices, done, fail)
        return True

    def on_device_changed(self, dev):
        if dev is None or dev.state not in ("device", "unauthorized"):
            self.agent = None
            self.title_widget.set_subtitle("")
            self.show_page("nophone")
            return
        self.title_widget.set_subtitle(dev.model)
        self.model = dev.model or "your phone"
        if dev.state == "unauthorized":
            self.agent = None
            self.show_page("unauthorized")
            return
        self.agent = ac.Agent(self.adb, dev.serial)
        self.reprobe()

    def reprobe(self):
        if not self.agent:
            return
        self.show_page("loading")
        agent, token, keys = self.agent, self.keys.token, self.keys

        def work():
            if not agent.installed():
                return "setup", None, None
            try:
                st = agent.status(token)
            except ac.AdbError:
                return "setup", None, None
            if st.get("version", 0) < ac.AGENT_VERSION and APK.exists():
                agent.install(APK)
                st = agent.status(token)
            if not st["owner"] or not st["paired"]:
                return "setup", st, None
            if not st["authorized"]:
                return "foreign", st, None
            other = keys.other_phone(st)
            if other:
                return "limit", st, other
            keys.claim(st)
            agent.allow_background()
            if st["selected"] and not st.get("mode"):
                st = agent.select(token, [])  # a list left from before Anchor/Release buttons
            return "main", st, agent.apps()

        def done(result):
            if agent is not self.agent:
                return
            page, st, apps = result
            if st:
                self.model = st.get("model") or self.model
                self.device_id = st.get("device_id")
                self.title_widget.set_subtitle(self.model)
            if page == "limit":
                self.limit_page.set_description(self.limit_text(apps) + "\n\nOr remove Anchor from "
                                                f"{self.model}: every hidden app on it comes back.")
            if page == "setup":
                self.update_setup_steps(installed=st is not None, st=st)
            elif page == "main":
                self.status = st
                self.selected = set(st["selected"]) if st.get("mode") else set()
                self.update_schedules()
                self.populate_apps(*apps)
                self.update_hero()
                self.update_never_allow()
                self.ensure_placeholders()
                if not st.get("install_blocks_set", True):
                    # First time with this phone: social media is on the 'Never allow' list by default.
                    self.save_install_blocks(catalog.defaults(),
                                             "Social media apps are now on your 'Never allow' list")
                if any(not x.get("packages") for x in st.get("schedules", [])):
                    # Version 3 had schedules for the whole list; they're per app now.
                    self.save_schedules(self.schedules, "Old schedules were removed: schedules are now set per app")
            self.show_page(page)

        def fail(e):
            if agent is not self.agent:
                return
            self.show_page("nophone")
            self.device_key = None  # retry on next poll
            self.toast(f"Couldn't talk to the phone: {e}")

        in_background(work, done, fail)

    def refresh_status(self):
        if not self.agent:
            return
        agent, token = self.agent, self.keys.token

        def done(st):
            if agent is not self.agent or self.working:
                return
            # The phone's clock changes every time; anything else changing means a real update.
            phone_list = set(st["selected"]) if st.get("mode") else set()
            same = phone_list == self.selected and {k: v for k, v in st.items() if k != "now"} == \
                {k: v for k, v in self.status.items() if k != "now"}
            if same:
                self.update_hero()  # only the countdown text can have moved on
            else:
                self.apply_status(st)

        in_background(lambda: agent.status(token), done, lambda e: None)

    # ---- Setup -------------------------------------------------------------------------

    def update_setup_steps(self, installed, st):
        states = [installed, bool(st and st["owner"]), bool(st and st["paired"])]
        for row, ok in zip(self.step_rows, states):
            row.set_visible_child_name("done" if ok else "todo")
        self.setup_button.set_sensitive(True)
        self.setup_button.set_label("Set up phone" if not any(states) else "Continue setup")

    def on_setup(self, _button):
        if not APK.exists():
            self.error_dialog("Companion app missing",
                              f"Anchor couldn't find {APK.name} next to the app. Rebuild it with android/build.sh.")
            return
        agent, token, keys = self.agent, self.keys.token, self.keys
        self.setup_button.set_sensitive(False)

        def mark(i, state):
            GLib.idle_add(lambda: self.step_rows[i].set_visible_child_name(state) and False)

        def work():
            mark(0, "working")
            st = None
            if agent.installed():
                try:
                    st = agent.status(token)
                except ac.AdbError:
                    st = None
            if st is None or st.get("version", 0) < ac.AGENT_VERSION:
                agent.install(APK)
                st = agent.status(token)
            if not st["paired"] and keys.other_phone(st):
                raise PhoneLimit(keys.other_phone(st))
            mark(0, "done")
            mark(1, "working")
            if not st["owner"]:
                agent.set_device_owner()
                st = agent.status(token)
            mark(1, "done")
            mark(2, "working")
            if not st["paired"]:
                st = agent.pair(token)
            elif not st["authorized"]:
                raise ac.SetupError("Already paired with another computer",
                                    "Use “Use a backup key…” in the menu to enter that computer's key.")
            keys.claim(st)
            mark(2, "done")
            return st

        def done(_st):
            self.toast("Your phone is ready. You can add your accounts back now.", timeout=6)
            self.reprobe()

        def fail(e):
            self.setup_button.set_sensitive(True)
            for row in self.step_rows:
                if row.get_visible_child_name() == "working":
                    row.set_visible_child_name("todo")
            if isinstance(e, PhoneLimit):
                self.limit_dialog(e.other)
            elif isinstance(e, ac.SetupError):
                self.error_dialog(e.title, e.body, e.details)
            else:
                self.error_dialog("Setup didn't finish", str(e))

        in_background(work, done, fail)

    def limit_dialog(self, other):
        name = other.get("model") or "the other phone"
        d = Adw.AlertDialog.new(
            "The free version works with one phone",
            self.limit_text(other) + f"\n\nIf {name} was factory reset, lost or replaced, you can forget it. "
            f"This computer then gets a new key, so {name} can't be controlled from here any more: "
            "if it still has anchored apps, they stay hidden until it's factory reset.")
        d.add_response("forget", f"Forget {name}")
        d.add_response("ok", "OK")
        d.set_response_appearance("forget", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_default_response("ok")
        d.set_close_response("ok")

        def response(_d, rid):
            if rid == "forget":
                self.keys.forget_phone()
                self.toast(f"{name} was forgotten. Write down the new backup key.")
                self.on_setup(None)

        d.connect("response", response)
        d.present(self)

    # ---- Main page ---------------------------------------------------------------------

    def populate_apps(self, apps, icons):
        self.populating = True
        for rows in (self.picked_list, self.other_list):
            rows.remove_all()
            rows.append(rows.header)
        self.rows = {}
        self.icons = icons
        self.installed = {a["pkg"] for a in apps}
        # Same kind of button, same width, so each kind lines up in a column.
        self.uninstall_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        self.anchor_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        labels = {a["pkg"]: a["label"] for a in apps}
        missing = [{"pkg": p, "label": catalog.name_for(p, labels), "system": False}
                   for p in sorted(self.selected) if p not in labels]
        for app in list(apps) + missing:
            row = Adw.ActionRow(title=app["label"], subtitle=app["pkg"])
            row.set_use_markup(False)
            row.set_title_lines(1)
            row.set_subtitle_lines(1)
            row.add_prefix(self.app_image(app["pkg"], app["label"]))
            # Left to right: Uninstall, schedule, Anchor/Release.
            row.uninstall_button = None
            if not app.get("system") and app["pkg"] in self.installed:
                uninstall = Gtk.Button(label="Uninstall", valign=Gtk.Align.CENTER,
                                       tooltip_text=f"Uninstall {app['label']} from your phone")
                uninstall.add_css_class("row-uninstall")
                uninstall.connect("clicked", lambda _b, a=app: self.on_uninstall_app(a))
                row.uninstall_button = uninstall
                slot = uninstall
            else:
                slot = Gtk.Box()  # keeps the columns lined up for apps that can't be uninstalled
            self.uninstall_group.add_widget(slot)
            row.add_suffix(slot)
            sched_button = Gtk.Button(icon_name="alarm-symbolic", valign=Gtk.Align.CENTER,
                                      tooltip_text=f"Schedule for {app['label']}")
            sched_button.add_css_class("flat")
            sched_button.add_css_class("sched-button")
            sched_button.connect("clicked", lambda _b, pkg=app["pkg"]: self.open_app_schedule(pkg))
            row.add_suffix(sched_button)
            row.sched_button = sched_button
            anchor_button = Gtk.Button(valign=Gtk.Align.CENTER)
            self.anchor_group.add_widget(anchor_button)
            anchor_button.add_css_class("row-anchor")
            anchor_button.connect("clicked", lambda _b, pkg=app["pkg"]: self.on_anchor_clicked(pkg))
            row.add_suffix(anchor_button)
            row.anchor_button = anchor_button
            # Clicking the row (not its buttons) opens the app's details; it doesn't anchor or release.
            row.set_activatable(True)
            row.connect("activated", lambda _r, a=app: self.open_app_details(a))
            row.pkg = app["pkg"]
            row.label = app["label"]
            row.sort_key = app["label"].casefold()
            row.search_text = (app["label"] + " " + app["pkg"]).casefold()
            self.list_for(row.pkg).append(row)
            self.rows[app["pkg"]] = row
        self.populating = False
        self.update_row_notes()
        self.update_hero()  # section counts

    def app_image(self, pkg, label):
        """The app's real icon when the phone sent one, else a round avatar with its initial."""
        png = self.icons.get(pkg)
        if png:
            image = Gtk.Image.new_from_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes.new(png)))
            image.set_pixel_size(40)
            image.add_css_class("app-icon")
            return image
        return Adw.Avatar(size=40, text=label, show_initials=True)

    def reload_apps(self):
        agent = self.agent

        def done(result):
            if agent is self.agent:
                self.populate_apps(*result)
                self.update_never_allow()

        in_background(agent.apps, done, lambda e: None)

    def list_for(self, pkg):
        return self.picked_list if pkg in self.selected else self.other_list

    def place_rows(self):
        """Moves each row into the section that matches its switch."""
        for pkg, row in self.rows.items():
            target = self.list_for(pkg)
            if row.get_parent() is not target:
                row.get_parent().remove(row)
                target.append(row)

    def filter_row(self, row):
        if getattr(row, "is_header", False):
            return True
        if not row.get_parent().is_open:
            return False
        q = self.search.get_text().strip().casefold()
        return not q or q in row.search_text

    def on_search_changed(self, _entry):
        searching = bool(self.search.get_text().strip())
        for rows in (self.picked_list, self.other_list):
            if searching:
                rows.set_open(True)  # never hide matches in a folded section
            rows.placeholder_label.set_label("No apps match" if searching else rows.empty_text)
            rows.invalidate_filter()

    def on_anchor_clicked(self, pkg):
        """Anchor (hide now) or Release (bring back now) one app."""
        if pkg in self.selected:
            self.selected.discard(pkg)
        else:
            self.selected.add(pkg)
        # Move the row after the click has finished being handled.
        GLib.idle_add(lambda: self.place_rows() and False)
        self.update_row_notes()
        self.update_hero()
        if self.sync_source:  # several quick clicks are sent together
            GLib.source_remove(self.sync_source)
        self.sync_source = GLib.timeout_add(250, self.sync_selection)

    def sync_selection(self):
        self.sync_source = None
        agent, token, packages = self.agent, self.keys.token, set(self.selected)
        mode = self.status.get("mode")
        before = set(self.status.get("blocked", []))
        self.working = True

        def work():
            if packages and mode is None:
                return agent.shift(token, packages)  # first app anchored: start anchoring
            if not packages and mode is not None:
                agent.select(token, packages)
                return agent.end_anchoring(token)  # last app released: stop (schedules keep running)
            return agent.select(token, packages)

        def done(st):
            self.working = False
            self.apply_status(st, keep_selection=bool(self.sync_source))
            self.toast_changes(before, set(st["blocked"]), set(st["failed"]) & packages)

        def fail(e):
            self.working = False
            self.toast(f"Couldn't reach the phone: {e}")
            self.refresh_status()

        in_background(work, done, fail)
        return False

    def toast_changes(self, before, after, refused):
        """While anchored, confirms what each switch just did on the phone."""
        def names(pkgs):
            labels = sorted(self.rows[p].label if p in self.rows else p for p in pkgs)
            return labels[0] if len(labels) == 1 else plural(len(labels), "app")

        hidden, back = after - before, before - after
        if hidden:
            self.toast(f"{names(hidden)} anchored: hidden from your phone")
        if back:
            self.toast(f"{names(back)} released: back on your phone")
        if refused:
            self.toast(f"{names(refused)} can't be hidden (protected by Android)")

    def apply_status(self, st, keep_selection=False):
        self.status = st
        if not keep_selection and not self.sync_source:
            new = set(st["selected"]) if st.get("mode") else set()
            if new != self.selected:
                self.selected = new
                self.place_rows()
        self.update_schedules()
        self.update_hero()
        self.update_row_notes()
        self.update_never_allow()

    def update_row_notes(self):
        st = self.status
        shifted = st.get("shifted", False)
        failed = set(st.get("failed", []))
        blocked = set(st.get("blocked", []))
        scheduled_now = st.get("scheduled_now", {})
        removed = st.get("permissions_removed", {})
        for pkg, row in self.rows.items():
            picked = pkg in self.selected
            windows = self.app_schedules(pkg)
            if picked and pkg not in getattr(self, "installed", set()):
                note = "Not on your phone · can't be installed while anchored"
            elif (picked or windows) and pkg in failed:
                note = "Can't be hidden: protected by Android"
            elif picked:
                note = "Hidden" if pkg in blocked else "Hiding…"
            elif pkg in scheduled_now:
                note = f"Hidden by its schedule until {clock(scheduled_now[pkg])}"
            elif pkg in blocked:
                note = "Bringing back…"
            elif windows:
                note = self.schedule_summary(pkg)
            else:
                note = pkg
            if pkg in blocked and removed.get(pkg) and note != "Bringing back…":
                note += f" · {plural(removed[pkg], 'permission')} removed"
            # Only touch what changed: setting the same text still makes GTK redraw the row.
            if row.get_subtitle() != note:
                row.set_subtitle(note)
            label = "Release" if picked else "Anchor"
            if row.anchor_button.get_label() != label:
                row.anchor_button.set_label(label)
                row.anchor_button.set_tooltip_text(f"{label} {row.label}")
            if picked:
                row.anchor_button.add_css_class("release")
            else:
                row.anchor_button.remove_css_class("release")
            if any(w.get("enabled", True) for w in windows):
                row.sched_button.add_css_class("accent")
            else:
                row.sched_button.remove_css_class("accent")

    def update_hero(self):
        st = self.status
        mode, ends = st.get("mode"), st.get("ends", 0)
        scheduled_now = st.get("scheduled_now", {})
        n = len(self.selected)
        anchored = n > 0
        on_schedule = ""
        if scheduled_now:
            names = sorted(self.rows[p].label if p in self.rows else p for p in scheduled_now)
            who = names[0] if len(names) == 1 else (", ".join(names[:-1]) + " and " + names[-1])
            verb = "is" if len(names) == 1 else "are"
            on_schedule = f"{who} {verb} hidden by {'its' if len(names) == 1 else 'their'} schedule right now."

        self.hero_button.set_visible(anchored)
        self.pause_button.set_visible(bool(scheduled_now) and not anchored)
        if anchored or scheduled_now:
            self.hero.add_css_class("anchored")
            self.hero_icon.set_from_icon_name("anchor-orb-on")
        else:
            self.hero.remove_css_class("anchored")
            self.hero_icon.set_from_icon_name("anchor-orb-off")
        if anchored:
            if mode == "timer":
                self.hero_title.set_label(f"Anchored until {clock(ends)}")
                text = f"{plural(n, 'app')} hidden. They come back by themselves {countdown(ends)}."
            else:
                self.hero_title.set_label("Anchored")
                text = f"{plural(n, 'app')} hidden from {self.model} until you release them."
            if on_schedule:
                text += f" {on_schedule} Release all also pauses that until it ends."
            self.hero_button.set_label("Release all")
            self.hero_button.add_css_class("release")
        else:
            self.hero_title.set_label("On schedule" if scheduled_now else "Not anchored")
            text = on_schedule or ("Tap Anchor on any app below to hide it from your phone right away. "
                                   "Only this computer can bring it back.")
        self.hero_subtitle.set_label(text)
        self.hero_button.set_sensitive(not self.working)
        self.update_sections(anchored, n)

    def update_sections(self, anchored, n):
        # The Anchored apps section only shows when something is anchored (or a search is on).
        self.picked_title.section.set_visible(n > 0)
        self.picked_title.set_label(f"Anchored apps ({n})")
        self.picked_hint.set_label("Hidden from your phone. Tap Release to bring one back.")
        others = sum(1 for p in self.rows if p not in self.selected)
        self.other_title.set_label(f"{'All other apps' if n else 'Your apps'} ({others})")
        self.other_hint.set_label("Tap Anchor to hide an app from your phone right away.")

    def on_hero_clicked(self, _button):
        """Release all: confirmed with the computer's admin password first."""
        if not self.selected:
            return
        self.hero_button.set_sensitive(False)

        def done(result):
            self.hero_button.set_sensitive(True)
            if result == "ok":
                self.run_shift(None, unshift=True)
            elif result == "cancelled":
                self.toast("Release all cancelled · your apps stay anchored")
            elif result == "missing":
                self.error_dialog("Can't ask for your password",
                                  "Anchor uses the system's password prompt (pkexec), which isn't installed. "
                                  "Install it with: sudo apt install pkexec")
            else:
                self.toast("Password not accepted · your apps stay anchored")

        in_background(system_password_check, done, lambda e: done("failed"))

    def run_shift(self, minutes, unshift=False):
        if self.sync_source:
            GLib.source_remove(self.sync_source)
            self.sync_source = None
        agent, token = self.agent, self.keys.token
        packages = set(self.selected)
        was_anchored = bool(packages)
        self.working = True
        self.hero_button.set_sensitive(False)
        self.pause_button.set_sensitive(False)

        def work():
            return agent.unshift(token) if unshift else agent.shift(token, packages, minutes)

        def done(st):
            self.working = False
            self.pause_button.set_sensitive(True)
            self.apply_status(st)
            if unshift:
                paused = st.get("paused", {})
                msg = "Released · all apps are back" if was_anchored else "Scheduled apps are back"
                if paused:
                    msg += f" · schedules paused until {clock(max(paused.values()))}"
            elif minutes:
                msg = f"Auto-release at {clock(st['ends'])} · {plural(len(packages), 'app')} come back then"
            else:
                msg = "Anchored until you release them"
            self.toast(msg)

        def fail(e):
            self.working = False
            self.pause_button.set_sensitive(True)
            self.update_hero()
            self.error_dialog("Couldn't reach the phone" if isinstance(e, ac.AdbError) else "The phone said no",
                              str(e))

        in_background(work, done, fail)

    # ---- App details -------------------------------------------------------------------

    def open_app_details(self, app):
        pkg, label = app["pkg"], app["label"]
        d = Adw.Dialog(title=label, content_width=460, content_height=640)
        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        page = Adw.PreferencesPage()
        view.set_content(page)
        d.set_child(view)

        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_bottom=6)
        icon = self.app_image(pkg, label)
        if isinstance(icon, Gtk.Image):
            icon.set_pixel_size(72)
        else:
            icon.set_size(72)
        icon.set_halign(Gtk.Align.CENTER)
        top.append(icon)
        name = Gtk.Label(label=label, wrap=True, justify=Gtk.Justification.CENTER)
        name.add_css_class("title-2")
        top.append(name)
        sub_label = Gtk.Label(label=pkg)
        sub_label.add_css_class("dim-label")
        sub_label.add_css_class("caption")
        top.append(sub_label)
        header = Adw.PreferencesGroup()
        header.add(top)
        page.add(header)

        about = Adw.PreferencesGroup(title="About")
        page.add(about)
        perms = Adw.PreferencesGroup(title="Permissions")
        page.add(perms)
        loading = Adw.ActionRow(title="Loading…")
        loading.add_suffix(Gtk.Spinner(spinning=True))
        about.add(loading)
        d.app, d.about, d.perms, d.perm_rows = app, about, perms, {}
        d.page_widgets = [loading]
        d.present(self)
        self.details = d

        agent = self.agent

        def done(info):
            if self.details is d:
                self.fill_app_details(d, info)

        def fail(e):
            if self.details is d:
                loading.set_title("Couldn't read this app's details")
                loading.set_subtitle(str(e))

        in_background(lambda: agent.app_info(pkg), done, fail)

    def status_text(self, pkg):
        st = self.status
        if pkg in self.selected:
            return "Anchored: hidden from your phone"
        if pkg in st.get("scheduled_now", {}):
            return f"Hidden by its schedule until {clock(st['scheduled_now'][pkg])}"
        if pkg in st.get("install_caught", []):
            return "On Never allow: hidden"
        if pkg in {a["pkg"] for a in st.get("install_blocks", [])}:
            return "On Never allow (was already on your phone, so not affected)"
        if self.app_schedules(pkg):
            return "Has a schedule"
        return "Not anchored"

    def fill_app_details(self, d, info):
        for w in d.page_widgets:
            d.about.remove(w)
        d.page_widgets = []

        def date(ms):
            return datetime.fromtimestamp(ms / 1000).strftime("%-d %b %Y") if ms else "—"

        rows = [
            ("Status", self.status_text(info["pkg"])),
            ("Version", info.get("version") or "—"),
            ("Installed", date(info.get("installed"))),
            ("Last updated", date(info.get("updated"))),
            ("Type", "Came with the phone" if info.get("system") else "Installed by you"),
        ]
        for title, value in rows:
            row = Adw.ActionRow(title=title, subtitle=value)
            row.add_css_class("property")
            row.set_subtitle_selectable(True)
            d.about.add(row)
            d.page_widgets.append(row)
        self.fill_permissions(d, info)

    def fill_permissions(self, d, info):
        for row in d.perm_rows.values():
            d.perms.remove(row)
        d.perm_rows = {}
        if getattr(d, "perm_empty", None):
            d.perms.remove(d.perm_empty)
            d.perm_empty = None
        blocked = info.get("blocked")
        label = info.get("label", d.app["label"])
        d.perms.set_description(
            f"Permissions are removed while {label} is blocked, and come back when you release it."
            if blocked else "Changes apply on your phone right away. You can still change them in the phone's Settings.")
        if not info.get("permissions"):
            d.perm_empty = Adw.ActionRow(title="No permissions to manage",
                                         subtitle=f"{label} doesn't ask for any permissions you grant.")
            d.perms.add(d.perm_empty)
            return
        named = [(friendly(p["name"], p["label"]), p) for p in info["permissions"]]
        for (title, subtitle), perm in sorted(named, key=lambda x: x[0][0].casefold()):
            row = Adw.SwitchRow(title=title, subtitle=subtitle)
            row.set_active(perm["granted"])
            row.set_sensitive(not blocked)
            if blocked and perm.get("had"):
                row.set_subtitle(" · ".join(x for x in (row.get_subtitle(), "comes back when released") if x))
            row.connect("notify::active", self.on_permission_switched, d, perm["name"])
            d.perms.add(row)
            d.perm_rows[perm["name"]] = row

    def on_permission_switched(self, row, _pspec, d, permission):
        if getattr(d, "updating", False):
            return
        agent, token, pkg, grant = self.agent, self.keys.token, d.app["pkg"], row.get_active()
        row.set_sensitive(False)

        title = row.get_title()

        def done(info):
            self.toast(f"{title}: {'allowed' if grant else 'removed'} for {d.app['label']}")
            if self.details is not d:
                return  # the window was closed or replaced meanwhile
            d.updating = True
            self.fill_permissions(d, info)
            d.updating = False

        def fail(e):
            if self.details is not d:
                return
            d.updating = True
            row.set_active(not grant)
            d.updating = False
            row.set_sensitive(True)
            self.toast(f"Couldn't change that permission: {e}")

        in_background(lambda: agent.set_permission(token, pkg, permission, grant), done, fail)

    def on_uninstall_app(self, app):
        d = Adw.AlertDialog.new(
            f"Uninstall {app['label']}?",
            f"{app['label']} and its data are removed from your phone.")
        d.add_response("cancel", "Cancel")
        d.add_response("uninstall", "Uninstall")
        d.set_response_appearance("uninstall", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_close_response("cancel")

        def response(_d, rid):
            if rid != "uninstall":
                return
            agent, token, pkg = self.agent, self.keys.token, app["pkg"]
            self.working = True

            def work():
                agent.uninstall_app(token, pkg)
                for _ in range(40):  # the phone uninstalls in the background
                    if not agent.installed_package(pkg):
                        break
                    time.sleep(0.25)
                return agent.status(token)

            def done(st):
                self.working = False
                self.apply_status(st)
                self.toast(f"{app['label']} uninstalled")
                self.reload_apps()
                self.ensure_placeholders()

            def fail(e):
                self.working = False
                self.error_dialog(f"Couldn't uninstall {app['label']}", str(e))

            in_background(work, done, fail)

        d.connect("response", response)
        d.present(self)

    def time_picker(self, minutes):
        """Two spin buttons (hours, minutes). Returns (widget, read) where read() gives minutes."""
        box = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER)

        def spin(value, upper):
            sb = Gtk.SpinButton.new_with_range(0, upper, 1)
            sb.set_wrap(True)
            sb.set_orientation(Gtk.Orientation.VERTICAL)
            sb.set_numeric(True)
            sb.set_value(value)
            sb.add_css_class("time-spin")
            sb.connect("output", lambda b: b.set_text(f"{int(b.get_value()):02d}") or True)
            return sb

        hours, mins = spin(minutes // 60, 23), spin(minutes % 60, 59)
        colon = Gtk.Label(label=":")
        colon.add_css_class("title-2")
        for w in (hours, colon, mins):
            box.append(w)
        return box, lambda: int(hours.get_value()) * 60 + int(mins.get_value())

    # ---- Schedules -----------------------------------------------------------------------

    def app_schedules(self, pkg):
        return [x for x in self.schedules if pkg in x.get("packages", [])]

    def label_for(self, pkg):
        return self.rows[pkg].label if pkg in self.rows else pkg

    def schedule_summary(self, pkg):
        windows = self.app_schedules(pkg)
        if len(windows) == 1:
            w = windows[0]
            text = f"{days_text(w['days'])} · {hours_text(w['start'], w['end'])}"
            if not w.get("enabled", True):
                text += " · Off"
        else:
            on = sum(1 for w in windows if w.get("enabled", True))
            text = plural(len(windows), "schedule") + ("" if on == len(windows) else f" · {on} on")
        paused = self.status.get("paused", {})
        until = [paused[w["id"]] for w in windows if w["id"] in paused]
        if until:
            text += f" · Paused until {clock(max(until))}"
        return text

    def update_schedules(self):
        self.schedules = [x for x in self.status.get("schedules", []) if x.get("packages")]
        if self.app_dialog:
            self.fill_app_schedule(*self.app_dialog[1:])

    def open_app_schedule(self, pkg):
        label = self.label_for(pkg)
        d = Adw.AlertDialog.new(
            f"{label} schedule",
            f"Hide {label} from your phone at these times, even when you're not anchored. "
            "Your phone does this by itself; it doesn't need to be plugged in.")
        rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        rows.add_css_class("boxed-list")
        rows.connect("row-activated", lambda _l, row: row.window is not False and self.edit_window(pkg, row.window))
        d.set_extra_child(rows)
        d.add_response("close", "Done")
        d.set_default_response("close")
        d.set_close_response("close")
        d.connect("response", lambda *_: setattr(self, "app_dialog", None))
        self.app_dialog = (d, pkg, rows)
        self.fill_app_schedule(pkg, rows)
        d.present(self)

    def fill_app_schedule(self, pkg, rows):
        rows.remove_all()
        paused = self.status.get("paused", {})
        hidden_until = self.status.get("scheduled_now", {}).get(pkg)
        if hidden_until:
            now_row = Adw.ActionRow(title=f"Hidden right now, until {clock(hidden_until)}", activatable=False)
            now_row.add_prefix(Gtk.Image(icon_name="changes-prevent-symbolic"))
            now_row.window = False
            rows.append(now_row)
        for w in self.app_schedules(pkg):
            row = Adw.ActionRow(title=days_text(w["days"]), activatable=True)
            subtitle = hours_text(w["start"], w["end"])
            if not w.get("enabled", True):
                subtitle += " · Off"
            elif w["id"] in paused:
                subtitle += f" · Paused until {clock(paused[w['id']])}"
            row.set_subtitle(subtitle)
            row.add_prefix(Gtk.Image(icon_name="alarm-symbolic"))
            delete = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Delete")
            delete.add_css_class("flat")
            delete.connect("clicked", lambda _b, wid=w["id"]: self.delete_window(wid))
            row.add_suffix(delete)
            switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=w.get("enabled", True))
            switch.connect("notify::active", lambda sw, _p, wid=w["id"]: self.toggle_window(wid, sw.get_active()))
            row.add_suffix(switch)
            row.window, row.switch, row.delete = w, switch, delete
            rows.append(row)
        add = Adw.ActionRow(title="Add a time", activatable=True)
        add.add_prefix(Gtk.Image(icon_name="list-add-symbolic"))
        add.window = None
        rows.append(add)

    def describe(self, w):
        return f"{self.label_for(w['packages'][0])}: {days_text(w['days'])} {hours_text(w['start'], w['end'])}"

    def toggle_window(self, wid, enabled):
        w = next((x for x in self.schedules if x["id"] == wid), None)
        if w is None or w.get("enabled", True) == enabled:
            return
        self.save_schedules([dict(x, enabled=enabled) if x["id"] == wid else x for x in self.schedules],
                            f"{self.describe(w)} turned {'on' if enabled else 'off'}")

    def delete_window(self, wid):
        w = next(x for x in self.schedules if x["id"] == wid)
        self.save_schedules([x for x in self.schedules if x["id"] != wid], f"{self.describe(w)} deleted")

    def edit_window(self, pkg, window):
        new = window is None
        label = self.label_for(pkg)
        window = window or {"id": uuid.uuid4().hex[:8], "name": label, "enabled": True, "packages": [pkg],
                            "days": [1, 2, 3, 4, 5, 6, 7], "start": "22:30", "end": "07:00"}
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        days_box = Gtk.Box(halign=Gtk.Align.CENTER)
        days_box.add_css_class("linked")
        day_buttons = []
        for i, name in enumerate(DAY_NAMES, start=1):
            b = Gtk.ToggleButton(label=name, active=i in window["days"])
            b.add_css_class("day-toggle")
            days_box.append(b)
            day_buttons.append(b)
        content.append(days_box)

        def to_min(hhmm):
            h, m = hhmm.split(":")
            return int(h) * 60 + int(m)

        start_picker, read_start = self.time_picker(to_min(window["start"]))
        end_picker, read_end = self.time_picker(to_min(window["end"]))
        times = Gtk.Box(spacing=18, halign=Gtk.Align.CENTER)
        for caption_text, picker in (("From", start_picker), ("To", end_picker)):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            caption = Gtk.Label(label=caption_text)
            caption.add_css_class("caption-heading")
            col.append(caption)
            col.append(picker)
            times.append(col)
        content.append(times)
        note = Gtk.Label(label="If the end is earlier than the start, it ends the next morning. "
                               "The same start and end time means all day.",
                         wrap=True, justify=Gtk.Justification.CENTER, max_width_chars=40)
        note.add_css_class("dim-label")
        note.add_css_class("caption")
        content.append(note)

        d = Adw.AlertDialog.new(f"{'Add a time' if new else 'Edit time'} for {label}", None)
        d.set_extra_child(content)
        d.add_response("cancel", "Cancel")
        d.add_response("save", "Save")
        d.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        d.set_default_response("save")
        d.set_close_response("cancel")
        d.day_buttons, d.read_start, d.read_end = day_buttons, read_start, read_end

        def response(_d, rid):
            if rid != "save":
                return
            days = [i for i, b in enumerate(day_buttons, start=1) if b.get_active()]
            if not days:
                self.error_dialog("Pick at least one day", "Choose the days this time applies to.")
                return
            start, end = read_start(), read_end()
            item = dict(window, days=days, start=f"{start // 60:02d}:{start % 60:02d}",
                        end=f"{end // 60:02d}:{end % 60:02d}")
            updated = self.schedules + [item] if new else [item if x["id"] == item["id"] else x for x in self.schedules]
            self.save_schedules(updated, f"{self.describe(item)} saved")

        d.connect("response", response)
        d.present(self)

    def save_schedules(self, schedules, message):
        agent, token = self.agent, self.keys.token
        self.working = True

        def done(st):
            self.working = False
            self.apply_status(st)
            if message:
                self.toast(message)

        def fail(e):
            self.working = False
            self.update_schedules()
            self.error_dialog("Couldn't save the schedule", str(e))

        in_background(lambda: agent.set_schedules(token, schedules), done, fail)

    # ---- Menu actions --------------------------------------------------------------------

    def on_backup(self):
        d = Adw.AlertDialog.new(
            "Backup key",
            "This key is what lets a computer release your apps. Keep a copy somewhere you can't "
            "reach on impulse (a password manager, a note in a drawer) in case this computer is lost.")
        key = Gtk.Label(label=ac.KeyStore.format(self.keys.token), selectable=True, wrap=True)
        key.add_css_class("key-label")
        d.set_extra_child(key)
        d.add_response("copy", "Copy")
        d.add_response("close", "Close")
        d.set_default_response("close")

        def response(_d, rid):
            if rid == "copy":
                self.get_clipboard().set(ac.KeyStore.format(self.keys.token))
                self.toast("Backup key copied")

        d.connect("response", response)
        d.present(self)

    def on_import(self):
        d = Adw.AlertDialog.new(
            "Use a backup key",
            "Enter the backup key of the computer your phone is paired with. This computer will "
            "then be able to control the phone. It replaces this computer's current key.")
        entry = Gtk.Entry(placeholder_text="XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX", activates_default=True)
        entry.add_css_class("monospace")
        d.set_extra_child(entry)
        d.add_response("cancel", "Cancel")
        d.add_response("use", "Use key")
        d.set_response_appearance("use", Adw.ResponseAppearance.SUGGESTED)
        d.set_default_response("use")
        d.set_close_response("cancel")

        def response(_d, rid):
            if rid != "use":
                return
            try:
                self.keys.set(ac.KeyStore.parse(entry.get_text()))
            except ValueError as e:
                self.error_dialog("That key doesn't look right", str(e))
                return
            self.toast("Backup key saved")
            self.reprobe()

        d.connect("response", response)
        d.present(self)

    def on_remove(self):
        if not self.agent:
            return
        d = Adw.AlertDialog.new(
            f"Remove Anchor from {self.model}?",
            "Every hidden app comes back and Anchor is uninstalled from the phone. "
            "You can set it up again any time.")
        d.add_response("cancel", "Cancel")
        d.add_response("remove", "Remove")
        d.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_close_response("cancel")

        def response(_d, rid):
            if rid != "remove":
                return
            agent, token, device_id = self.agent, self.keys.token, self.device_id
            self.show_page("loading")

            def work():
                try:
                    agent.release(token)
                except ac.AgentError as e:
                    if e.code != "not_owner":
                        raise
                agent.uninstall()
                if device_id:
                    self.keys.free_slot(device_id)  # free version: another phone can be set up now

            def done(_):
                self.toast("Anchor was removed from the phone")
                self.reprobe()

            def fail(e):
                self.reprobe()
                self.error_dialog("Couldn't remove Anchor", str(e))

            in_background(work, done, fail)

        d.connect("response", response)
        d.present(self)

    def on_uninstall_desktop(self):
        d = Adw.AlertDialog.new(
            "Uninstall Anchor from this computer?",
            "This removes the Anchor app, its launcher and your saved key from this computer. "
            "It does not touch your phone.\n\n"
            "If a phone is still anchored to this computer, remove Anchor from the phone first "
            "(the option above). Uninstalling deletes the key, and without it a phone that is "
            "still anchored can only be recovered with a factory reset.")
        d.add_response("cancel", "Cancel")
        d.add_response("uninstall", "Uninstall")
        d.set_response_appearance("uninstall", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_close_response("cancel")

        def response(_d, rid):
            if rid != "uninstall":
                return
            self.show_page("loading")

            def work():
                data_home = Path(GLib.get_user_data_dir())
                if PACKAGED:  # installed from the .deb: remove the key, then the package itself
                    shutil.rmtree(data_home / "anchor", ignore_errors=True)
                    if not (shutil.which("pkexec") and os.access(UNINSTALL_HELPER, os.X_OK)):
                        return "package"
                    code = subprocess.run(["pkexec", "--disable-internal-agent", UNINSTALL_HELPER],
                                          timeout=600).returncode
                    return True if code == 0 else "package"
                targets = [
                    data_home / "anchor-app",
                    Path.home() / ".local" / "bin" / "anchor",
                    data_home / "applications" / f"{APP_ID}.desktop",
                    data_home / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg",
                    data_home / "anchor",  # the saved key and settings
                ]
                for p in targets:
                    try:
                        if p.is_dir() and not p.is_symlink():
                            shutil.rmtree(p)
                        elif p.exists() or p.is_symlink():
                            p.unlink()
                    except FileNotFoundError:
                        pass
                # The polkit files are owned by root; only prompt for a password if they exist.
                system_files = [p for p in (RELEASE_POLICY, RELEASE_CHECK) if os.path.exists(p)]
                if not system_files:
                    return True
                if not shutil.which("pkexec"):
                    return False
                if os.access(UNINSTALL_HELPER, os.X_OK):  # worded prompt, and leaves the .deb's files alone
                    command = ["pkexec", "--disable-internal-agent", UNINSTALL_HELPER]
                else:  # installed before the helper existed
                    command = ["pkexec", "rm", "-f", *system_files]
                return subprocess.run(command, timeout=300).returncode == 0

            def done(system_removed):
                msg = "Anchor has been removed from this computer."
                if system_removed == "package":  # the password prompt was cancelled or failed
                    msg = ("Your saved key was removed, but the Anchor app itself is still installed. "
                           "To remove it, run:\nsudo apt remove anchor")
                elif not system_removed:
                    msg += ("\n\nThe system password-prompt files were left in place. "
                            f"Remove them with:\nsudo rm -f {RELEASE_POLICY} {RELEASE_CHECK}")
                final = Adw.AlertDialog.new("Uninstalled", msg)
                final.add_response("close", "Close")
                final.set_close_response("close")
                final.connect("response", lambda *_: self.get_application().quit())
                final.present(self)

            def fail(e):
                self.reprobe()
                self.error_dialog("Couldn't uninstall Anchor", str(e))

            in_background(work, done, fail)

        d.connect("response", response)
        d.present(self)

    def on_check_updates(self):
        """Asks GitHub, only now, whether a newer Anchor is out (the only time the app goes online)."""
        def done(result):
            if result == updates.CURRENT:
                d = Adw.AlertDialog.new("You're up to date", "This is the newest version of Anchor.")
                d.add_response("close", "OK")
            elif result == updates.AVAILABLE and self.can_update_itself():
                d = Adw.AlertDialog.new("A new version of Anchor is available",
                                        "Anchor downloads it from GitHub, installs it over this one and restarts. "
                                        "Your key and settings stay.")
                d.add_response("later", "Not now")
                d.add_response("update", "Update")
                d.set_response_appearance("update", Adw.ResponseAppearance.SUGGESTED)
                d.set_default_response("update")
                d.set_close_response("later")
            elif result == updates.AVAILABLE:
                d = Adw.AlertDialog.new("A new version of Anchor is available",
                                        "Download it from GitHub and install it over this one. Your key and settings stay.")
                d.add_response("later", "Not now")
                d.add_response("download", "Download")
                d.set_response_appearance("download", Adw.ResponseAppearance.SUGGESTED)
                d.set_default_response("download")
                d.set_close_response("later")
            else:
                d = Adw.AlertDialog.new("Can't tell which version this is",
                                        "This copy of Anchor wasn't downloaded from GitHub, so there's nothing to compare it with. "
                                        "The newest version is always on the download page.")
                d.add_response("close", "Close")
                d.add_response("download", "Open downloads")
                d.set_close_response("close")
            def response(_d, rid):
                if rid == "download":
                    self.open_link(updates.download_page(UPDATE_CHANNEL))
                elif rid == "update":
                    self.install_update()

            d.connect("response", response)
            d.present(self)

        def fail(e):
            self.error_dialog("Couldn't check for updates",
                              "Anchor couldn't reach GitHub. Check your internet connection and try again.", str(e))

        self.toast("Checking for updates…")
        in_background(lambda: updates.check(UPDATE_CHANNEL), done, fail)

    def can_update_itself(self):
        """Only the .deb can: it ships the helper that installs a newer one (install.sh copies can't)."""
        return PACKAGED and os.access(UPDATE_HELPER, os.X_OK) and bool(shutil.which("pkexec"))

    def install_update(self):
        """Downloads the newest .deb, installs it after the computer's password, then restarts Anchor.
        The key and settings in ~/.local/share/anchor aren't touched."""
        self.toast("Downloading the new version…", timeout=10)

        def work():
            deb = updates.download(UPDATE_CHANNEL, "anchor-linux.deb")
            return subprocess.run(["pkexec", "--disable-internal-agent", UPDATE_HELPER, str(deb)],
                                  timeout=900).returncode

        def done(code):
            if code == 0:
                # Start the new version once this one has closed (only one Anchor runs at a time).
                subprocess.Popen(["sh", "-c", "sleep 1; exec anchor"], start_new_session=True)
                self.get_application().quit()
            elif code == 126:
                self.toast("Update cancelled")
            elif code == 127:
                self.toast("Password not accepted · Anchor wasn't updated")
            else:
                self.error_dialog("Couldn't update Anchor",
                                  "The new version couldn't be installed. You can download it from GitHub "
                                  "and install it yourself.")

        def fail(e):
            self.error_dialog("Couldn't update Anchor",
                              "Anchor couldn't download the new version. Check your internet connection "
                              "and try again.", str(e))

        in_background(work, done, fail)

    def open_link(self, url):
        Gtk.UriLauncher.new(url).launch(self, None, None)

    def on_donate(self):
        Gtk.UriLauncher.new(DONATE_URL).launch(self, None, None)

    def on_about(self):
        about = Adw.AboutDialog(
            application_name=WINDOW_TITLE, application_icon=APP_ID,
            comments="Block distracting apps on your Android phone. "
                     "Only this computer can unblock them.")
        about.add_credit_section("Developed by", ["Paulo Medeiros"])
        about.add_link("GitHub repository", WEBSITE)
        about.present(self)


# On X11, GTK 4 draws a menu's corners solid even with a compositor, so a rounded menu sits in a
# square frame. Square menus fill their frame exactly; Wayland keeps the rounded ones.
X11_CSS = "\npopover > contents { border-radius: 0; }\n"


def is_x11(display):
    return type(display).__name__ == "X11Display"


class AnchorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_startup(self):
        Adw.Application.do_startup(self)
        GLib.set_application_name("Anchor")
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        display = Gdk.Display.get_default()
        Gtk.IconTheme.get_for_display(display).add_search_path(str(HERE / "icons"))
        css = Gtk.CssProvider()
        css.load_from_string(CSS + (X11_CSS if is_x11(display) else ""))
        Gtk.StyleContext.add_provider_for_display(display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        Gtk.Window.set_default_icon_name(APP_ID)

    def do_activate(self):
        win = self.props.active_window or AnchorWindow(self)
        win.present()


if __name__ == "__main__":
    sys.exit(AnchorApp().run(sys.argv))
