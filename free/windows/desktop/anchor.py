#!/usr/bin/env python3
"""Anchor for Windows: block apps on your Android phone; only this computer can unblock them.

The same app as the Linux one (free/linux/desktop/anchor.py), drawn with Qt instead of GTK so it
looks and works the same on Windows. Everything that talks to the phone is shared code."""

import json
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from PySide6.QtCore import QObject, QPoint, QSize, Qt, QTimer, QUrl, Signal  # noqa: E402
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QPalette  # noqa: E402
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLineEdit,  # noqa: E402
                               QMainWindow, QMenu, QPlainTextEdit, QPushButton, QStackedWidget, QVBoxLayout,
                               QWidget)

import adbclient as ac  # noqa: E402
import catalog  # noqa: E402
import keysheet  # noqa: E402
import platform_support as plat  # noqa: E402
import theme  # noqa: E402
import updates  # noqa: E402
import widgets as w  # noqa: E402
from permnames import friendly  # noqa: E402
from timetext import DAY_NAMES, clock, countdown, days_text, hours_text, plural, screen_time  # noqa: E402

APP_ID = plat.APP_ID
APK = HERE / "anchor-agent.apk"
VERSION = "1.0"
WINDOW_TITLE = "Anchor - Free"
WEBSITE = "https://github.com/medpaf/anchor"
UPDATE_CHANNEL = "windows"  # Menu → Check for updates… compares with the "windows" release
DONATE_URL = "https://github.com/sponsors/medpaf"  # free version: Menu → Buy me a coffee
POLL_MS = 2000

RUNNING = set()  # background threads still at work (tests wait for these between cases)


class _Bridge(QObject):
    """Carries a callable from a worker thread to the Qt main thread."""
    call = Signal(object)


_bridge = None


def on_main(fn):
    """Runs fn() on the Qt main thread, soon. Safe to call from any thread."""
    _bridge.call.emit(fn)


def in_background(work, done=None, fail=None):
    """Runs work() on a thread, then done(result) or fail(exception) on the Qt main thread."""
    global _bridge
    if _bridge is None:
        _bridge = _Bridge()
        _bridge.call.connect(lambda fn: fn(), Qt.QueuedConnection)

    def runner():
        try:
            result = work()
        except Exception as e:  # noqa: BLE001 - shown to the user
            if fail:
                on_main(lambda err=e: fail(err))
            return
        if done:
            on_main(lambda: done(result))

    thread = threading.Thread(target=lambda: (runner(), RUNNING.discard(thread)), daemon=True)
    RUNNING.add(thread)
    thread.start()


def system_password_check():
    """Release all asks for this computer's password first (Windows' own dialog, or polkit)."""
    return plat.system_password_check()


class PhoneLimit(Exception):
    """Free version: this computer is already set up for a different phone."""

    def __init__(self, other):
        super().__init__("This computer is set up for another phone")
        self.other = other


class StepState(QStackedWidget):
    """A setup step's state on the right of its row: nothing, a spinner, or a check mark."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(26, 26)
        self.names = ["todo", "working", "done"]
        self.addWidget(QWidget())
        self.addWidget(w.Spinner(22))
        self.addWidget(w.image(w.symbol("check", theme.SUCCESS, 22)))

    def set_visible_child_name(self, name):
        self.setCurrentIndex(self.names.index(name))

    def get_visible_child_name(self):
        return self.names[self.currentIndex()]


class TimePicker(QWidget):
    """Hours and minutes, each with arrows above and below and the mouse wheel."""

    def __init__(self, minutes):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.values = [minutes // 60, minutes % 60]
        self.labels = []
        for i, upper in ((0, 23), (1, 59)):
            col = QVBoxLayout()
            col.setSpacing(2)
            up = w.icon_button("expand-less", "Later", lambda i=i, u=upper: self.step(i, 1, u), size=18)
            value = w.label("", "timeValue", align=Qt.AlignCenter)
            value.wheelEvent = lambda ev, i=i, u=upper: self.step(i, 1 if ev.angleDelta().y() > 0 else -1, u)
            down = w.icon_button("expand-more", "Earlier", lambda i=i, u=upper: self.step(i, -1, u), size=18)
            for x in (up, value, down):
                col.addWidget(x, 0, Qt.AlignHCenter)
            lay.addLayout(col)
            self.labels.append(value)
            if i == 0:
                lay.addWidget(w.label(":", "colon"), 0, Qt.AlignVCenter)
        self._show()

    def step(self, i, delta, upper):
        self.values[i] = (self.values[i] + delta) % (upper + 1)
        self._show()

    def set_minutes(self, minutes):
        self.values = [minutes // 60, minutes % 60]
        self._show()

    def _show(self):
        for value, n in zip(self.labels, self.values):
            value.setText(f"{n:02d}")

    def minutes(self):
        return self.values[0] * 60 + self.values[1]


class AboutDialog(w.Overlay):
    """Name and edition, description, credits and a link to the GitHub repository."""

    def __init__(self, window):
        super().__init__(window, 380)
        lay = QVBoxLayout(self.panel)
        lay.setContentsMargins(26, 14, 14, 26)
        lay.setSpacing(6)
        close = w.icon_button("close", "Close", self.close_overlay, size=18)
        lay.addWidget(close, 0, Qt.AlignRight)
        lay.addWidget(w.image(w.picture("app.anchor.Desktop.svg", 112)), 0, Qt.AlignHCenter)
        self.name = w.label(WINDOW_TITLE, "nameTitle", align=Qt.AlignCenter)
        lay.addWidget(self.name)
        lay.addSpacing(8)
        lay.addWidget(w.label("Block distracting apps on your Android phone. Only this computer can "
                              "unblock them.", "dialogBody", wrap=True, align=Qt.AlignCenter))
        lay.addSpacing(10)
        credits = w.Group("Developed by")
        credits.add(w.Row("Paulo Medeiros"))
        lay.addWidget(credits)
        lay.addSpacing(6)
        self.site = site = w.button("GitHub repository", "pill", WEBSITE, lambda: QDesktopServices.openUrl(QUrl(WEBSITE)))
        lay.addWidget(site, 0, Qt.AlignHCenter)

    def get_application_name(self):
        return self.name.text()

    def get_website(self):
        return WEBSITE


def write_key_pdf(path, items):
    """Draws the backup key page (keysheet.page) as a one-page A4 PDF with Qt."""
    from PySide6.QtCore import QMarginsF, QRect
    from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

    writer = QPdfWriter(str(path))
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(0, 0, 0, 0)))
    writer.setResolution(72)  # one unit = one point, like the Linux version
    width, margin = 595, 64
    styles = {  # size, bold, monospace, space before
        "title": (24, True, False, 0), "key": (16, True, True, 22), "small": (10, False, False, 14),
        "heading": (13, True, False, 22), "text": (11, False, False, 8),
    }
    painter = QPainter()
    if not painter.begin(writer):  # Qt doesn't raise when it can't write there
        raise OSError(f"Can't write to {path}")
    y = margin
    for style, text in items:
        size, bold, mono, before = styles[style]
        font = QFont("Consolas" if mono else "Segoe UI")
        font.setStyleHint(QFont.Monospace if mono else QFont.SansSerif)
        font.setPointSizeF(size)
        font.setBold(bold)
        painter.setFont(font)
        y += before
        inset = 16 if mono else 0
        area = QRect(margin + inset, y, width - 2 * margin - 2 * inset, 2000)
        box = painter.boundingRect(area, Qt.TextWordWrap, text)
        if style == "key":  # the key on a light box, easy to read and copy
            painter.fillRect(QRect(margin, y, width - 2 * margin, box.height() + 28), QColor("#F0EBFA"))
            y += 14
            area.moveTop(y)
        painter.setPen(QColor("#54545F" if style == "small" else "#141219"))
        painter.drawText(area, Qt.TextWordWrap, text)
        y += box.height() + (14 if style == "key" else 0)
    painter.end()


class AnchorWindow(QMainWindow):
    def __init__(self, app=None):
        super().__init__()
        # The title bar says just "Anchor" (the heading inside the window shows the version). Qt adds
        # the app's name to any other title, which made it "Anchor - Free - Anchor".
        self.setWindowTitle("Anchor")
        self.setWindowIcon(QIcon(w.picture("app.anchor.Desktop.svg", 128)))
        self.resize(580, 780)
        self.setMinimumSize(440, 480)  # Windows' Segoe UI is wider than Linux fonts: 400 scrolled sideways
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
        self.populating = False
        self.schedules = []
        self.app_dialog = None
        self.details = None
        self.icons = {}
        self.installed = set()
        self.install_blocks = []
        self.never_key = None
        self.placing = False
        self.placeholder_failed = {}  # pkg -> why the placeholder couldn't be installed
        self.sync_timer = QTimer(self, singleShot=True, interval=250)
        self.sync_timer.timeout.connect(self.sync_selection)

        self.build_ui()
        self.install_actions()
        if self.adb:
            self.show_page("nophone")
            self.start_polling()
            self.poll()
        else:
            self.show_page("noadb")

    @property
    def sync_source(self):
        """The pending selection sync, if any (several quick clicks are sent together)."""
        return self.sync_timer if self.sync_timer.isActive() else None

    def start_polling(self):
        self.poll_timer = QTimer(self, interval=POLL_MS)
        self.poll_timer.timeout.connect(self.poll)
        self.poll_timer.start()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.fit_hero()

    def fit_hero(self):
        """On a narrow window the status card's button goes under the text, like on a phone, and
        the rows' Uninstall buttons shrink to icons."""
        compact = self.width() < 540
        if compact != getattr(self, "rows_compact", False):
            self.rows_compact = compact
            for row in self.rows.values():
                self.fit_uninstall(row)
        narrow = self.width() < 500
        if narrow == getattr(self, "hero_narrow", narrow):
            return
        self.hero_narrow = narrow
        self.hero_grid.removeItem(self.hero_actions)
        if narrow:
            self.hero_grid.addLayout(self.hero_actions, 1, 1, Qt.AlignLeft)
        else:
            self.hero_grid.addLayout(self.hero_actions, 0, 2, Qt.AlignVCenter)

    def showEvent(self, ev):
        super().showEvent(ev)
        plat.style_title_bar(int(self.winId()))

    # ---- UI construction ---------------------------------------------------------------

    def build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        header = QWidget()
        h = QHBoxLayout(header)
        h.setContentsMargins(14, 10, 10, 6)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.title_label = w.label(WINDOW_TITLE, "title", align=Qt.AlignCenter)
        self.subtitle_label = w.label("", "subtitle", align=Qt.AlignCenter)
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)
        h.addSpacing(36)
        h.addLayout(titles, 1)
        self.menu_button = w.icon_button("menu", "Menu", self.open_menu)
        h.addWidget(self.menu_button)
        lay.addWidget(header)

        self.stack = QStackedWidget()
        self.pages = {}
        self.add_page("noadb", w.StatusPage("warning", "adb is missing", plat.adb_install_hint()))
        self.add_page("nophone", w.StatusPage(
            "phone", "Connect your phone",
            "Plug your Android phone into this computer with a USB cable.<br><br>"
            "First time? Turn on USB debugging: open <b>Settings → About phone</b>, tap "
            "<b>Build number</b> seven times, then go to <b>Settings → System → Developer options</b> "
            "and switch on <b>USB debugging</b>.", spinner=True))
        self.add_page("unauthorized", w.StatusPage(
            "usb-allow", "Allow this computer",
            "Unlock your phone and tap <b>Allow</b> on the “Allow USB debugging?” prompt. "
            "Tick <b>Always allow from this computer</b> so you don't have to do it again.<br><br>"
            "No prompt? Unplug the cable and plug it back in.", spinner=True))
        self.add_page("loading", w.StatusPage(None, "Checking your phone…", "", spinner=True))
        self.add_page("foreign", self.build_foreign_page())
        self.add_page("limit", self.build_limit_page())
        self.add_page("setup", self.build_setup_page())
        self.add_page("main", self.build_main_page())
        lay.addWidget(self.stack, 1)
        self.toasts = w.Toasts(root)

    def add_page(self, name, widget):
        self.pages[name] = widget
        self.stack.addWidget(widget)

    def build_foreign_page(self):
        page = w.StatusPage("lock", "Anchored to another computer",
                            "This phone was set up with a different computer. To control it from here, "
                            "enter that computer's backup key.")
        page.extra.addWidget(w.button("Enter backup key", "cta", on_click=self.on_import), 0, Qt.AlignHCenter)
        return page

    def build_limit_page(self):
        # Free version: one phone per computer. Shown for a phone paired with this key that isn't that one.
        self.limit_page = w.StatusPage("phone", "The free version works with one phone")
        self.limit_page.extra.addWidget(
            w.button("Remove Anchor from this phone", "cta", on_click=self.on_remove), 0, Qt.AlignHCenter)
        return self.limit_page

    def limit_text(self, other):
        return (f"This computer is set up for {other.get('model') or 'another phone'}. To use Anchor with "
                f"{self.model}, connect that phone and remove Anchor from it first, or get Anchor Pro "
                "to use more phones.")

    def build_setup_page(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(24)

        top = QVBoxLayout()
        top.setSpacing(10)
        top.addWidget(w.image(w.picture("app.anchor.Desktop.svg", 96)), 0, Qt.AlignHCenter)
        top.addWidget(w.label("Set up your phone", "pageTitle", align=Qt.AlignCenter))
        intro = w.label("Anchor needs a small companion app on your phone. It becomes the phone's "
                        "device owner, which lets it block apps in a way the phone itself can't undo.",
                        "dim", wrap=True, align=Qt.AlignCenter)
        top.addWidget(intro)
        lay.addLayout(top)

        before = w.Group("Before you start")
        for icon, title, subtitle in [
            ("person", "Remove all accounts from the phone for a moment",
             "Settings → Passwords & accounts. Android only allows a device owner on a phone "
             "with no accounts. Add them back right after setup."),
            ("group", "Remove extra users and work profiles",
             "Guest users, work profiles, “Second space” or “Dual apps” must go too."),
        ]:
            before.add(w.Row(title, subtitle, prefix=w.image(w.symbol(icon, theme.DIM, 20)), subtitle_lines=0))
        lay.addWidget(before)

        steps = w.Group("Steps")
        self.step_rows = []
        for i, (title, subtitle) in enumerate([
            ("Install Anchor on the phone", "Copies the companion app over USB"),
            ("Make Anchor the device owner", "Lets Anchor block apps at the system level"),
            ("Pair with this computer", "From now on only this computer can release your apps"),
        ]):
            number = w.label(str(i + 1), "stepNumber", align=Qt.AlignCenter)
            row = w.Row(title, subtitle, prefix=number)
            state = StepState()
            row.add_suffix(state)
            steps.add(row)
            self.step_rows.append(state)
        lay.addWidget(steps)

        self.setup_button = w.button("Set up phone", "cta-big", on_click=lambda: self.on_setup(None))
        lay.addWidget(self.setup_button, 0, Qt.AlignHCenter)
        lay.addStretch(1)
        return w.scroller(w.Clamp(box, 560, (16, 18, 16, 32)))

    def build_main_page(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)

        # Status bar: emblem, what's going on, and the one main button.
        self.hero = QFrame()
        self.hero.setObjectName("hero")
        self.hero_grid = hero = QGridLayout(self.hero)
        hero.setContentsMargins(20, 18, 20, 18)
        hero.setHorizontalSpacing(16)
        hero.setVerticalSpacing(12)
        self.hero_icon = w.image(w.picture("anchor-orb-off.svg", 60))
        hero.addWidget(self.hero_icon, 0, 0, Qt.AlignVCenter)
        text = QVBoxLayout()
        text.setSpacing(3)
        self.hero_title = w.label("", "heroTitle")
        text.addSpacing(3)
        text.addWidget(self.hero_title)
        self.hero_subtitle = w.label("", "heroSubtitle", wrap=True)
        text.addWidget(self.hero_subtitle)
        hero.addLayout(text, 0, 1)
        hero.setColumnStretch(1, 1)
        self.hero_actions = actions = QVBoxLayout()
        actions.setSpacing(2)
        self.hero_button = w.button("Release all", "release", on_click=self.on_hero_clicked)
        actions.addWidget(self.hero_button, 0, Qt.AlignHCenter)
        self.pause_button = w.button("Bring back now", "link", "Bring scheduled apps back now",
                                     lambda: self.run_shift(None, unshift=True))
        actions.addWidget(self.pause_button, 0, Qt.AlignHCenter)
        hero.addLayout(actions, 0, 2, Qt.AlignVCenter)
        self.hero_narrow = False
        lay.addWidget(self.hero)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search your apps")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(w.symbol_icon("search", "rgba(238,234,247,0.7)", 18), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self.on_search_changed)
        lay.addWidget(self.search)

        self.never_section = w.Section("block", "Never allow", "Apps that can't be installed.", is_open=False)
        self.never_section.empty.hide()
        self.never_children = []
        lay.addWidget(self.never_section)

        # Two sections: the apps on your block list, and everything else. Anchoring or releasing an
        # app moves it from one to the other.
        self.picked_section = w.Section("anchor", empty_text="Nothing anchored. Tap Anchor on an app below.")
        self.other_section = w.Section("grid", empty_text="No other apps")
        for s in (self.picked_section, self.other_section):
            s.toggled.connect(lambda _open, s=s: self.apply_filter(s))
            lay.addWidget(s)
        lay.addStretch(1)
        return w.scroller(w.Clamp(box, 600))

    # ---- Never allow ---------------------------------------------------------------------

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
        self.never_section.set_title(f"Never allow ({len(blocks)})")
        self.never_section.set_hint("Apps that can't be installed.")
        self.never_section.clear()
        self.never_children = []
        for app in sorted(blocks, key=lambda a: a["name"].casefold()):
            pkg = app["pkg"]
            row = w.Row(app["name"], subtitle_lines=2)
            uninstall = None
            if pkg in caught:
                row.set_subtitle("Installed before the block was set up, so it's hidden. "
                                 "Uninstall it to stop it from being installed again.")
                uninstall = w.button("Uninstall", "pill-danger", f"Uninstall {app['name']} from your phone",
                                     lambda a=app: self.on_uninstall_blocked(a))
            elif pkg in kept:
                row.set_subtitle("Was already on your phone, so it's not affected. Anchor it to hide it.")
            elif pkg in placeholders:
                row.set_subtitle(pkg)  # blocked from being installed: show which package
            elif pkg in self.placeholder_failed:
                row.set_subtitle("Can be installed, but is hidden right away (the install couldn't be blocked)")
            else:
                row.set_subtitle("Blocking the install…" if self.placing else "Can't be used if installed")
            release = w.button("Release", "pill", f"Remove {app['name']} from Never allow",
                               lambda p=pkg: self.release_install_block(p))
            if uninstall:
                row.add_suffix(uninstall)
            row.add_suffix(release)
            row.pkg, row.release, row.uninstall = pkg, release, uninstall
            self.never_section.add(row)
            self.never_children.append(row)
        add = w.Row("Add an app…", prefix=w.image(w.symbol("add", theme.LILAC, 20)), clickable=True)
        add.activated.connect(self.on_add_install_block)
        self.never_section.add(add)
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

        def fail(_e):
            self.placing = False
            self.update_never_allow()

        in_background(work, done, fail)

    def on_uninstall_blocked(self, app):
        d = w.AlertDialog(self, f"Uninstall {app['name']}?",
                          f"{app['name']} and its data are removed from your phone. Anchor then stops it "
                          "from being installed again, until you release it here.")
        d.add_response("cancel", "Cancel")
        d.add_response("uninstall", "Uninstall")
        d.set_response_appearance("uninstall", "destructive")
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
        d = w.AlertDialog(self, f"Uninstall {names}?",
                          f"{names} {'is' if one else 'are'} on your phone. Adding {it} to Never allow "
                          f"uninstalls {it}, with {its} data, and stops {it} from being installed again "
                          f"until you release {it} here.")
        d.add_response("cancel", "Cancel")
        d.add_response("uninstall", "Uninstall")
        d.set_response_appearance("uninstall", "destructive")
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
        d = w.AlertDialog(self, "Never allow apps",
                          "Tick the apps, or paste a Play Store link. They can't be used on your phone, even "
                          "if installed, until you release them here. If one is on your phone, Anchor asks "
                          "before uninstalling it.", width=440)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        entry = QLineEdit()
        entry.setPlaceholderText("Play Store link or package name")
        entry.returnPressed.connect(lambda: d.emit_response("add"))
        lay.addWidget(entry)
        have = {a["pkg"] for a in self.install_blocks}
        options = [(p, n) for p, n in catalog.SOCIAL + catalog.SUGGESTIONS if p not in have]
        d.picks = {}  # pkg -> (name, tick box)
        if options:
            lay.addWidget(w.label("Suggestions", "captionHeading"))
            card = w.Card()
            for pkg, name in options:
                tick = QCheckBox()
                tick.setToolTip(f"Choose {name}")
                tick.setCursor(Qt.PointingHandCursor)
                row = w.Row(name, pkg, prefix=tick, clickable=True)
                row.activated.connect(tick.toggle)  # clicking the row ticks it
                d.picks[pkg] = (name, tick)
                card.add(row)
            area = w.scroller(card)
            area.setMaximumHeight(260)
            area.setMinimumHeight(min(260, 57 * len(options)))
            lay.addWidget(area)
            d.suggestions = card
        d.set_extra_child(content)
        d.add_response("cancel", "Cancel")
        d.add_response("add", "Add")
        d.set_response_appearance("add", "suggested")
        d.set_default_response("add")
        d.set_close_response("cancel")
        d.entry = entry

        def response(_d, rid):
            if rid != "add":
                return
            apps = [{"pkg": pkg, "name": name} for pkg, (name, tick) in d.picks.items() if tick.isChecked()]
            if entry.text().strip():
                try:
                    pkg = catalog.parse_app(entry.text())
                except ValueError as e:
                    self.error_dialog("That doesn't look like an app", str(e))
                    return
                labels = {r.pkg: r.label for r in self.rows.values()}
                if pkg not in {a["pkg"] for a in apps}:
                    apps.append({"pkg": pkg, "name": catalog.name_for(pkg, labels)})
            if apps:
                self.add_install_blocks(apps)

        d.connect("response", response)
        d.present(self)
        entry.setFocus()

    # ---- Menu ----------------------------------------------------------------------------

    def install_actions(self):
        self.actions = {}
        for name, text, handler in [
            ("refresh", "Refresh", self.reprobe),
            ("backup", "Backup key…", self.on_backup),
            ("import", "Use a backup key…", self.on_import),
            ("remove", "Remove Anchor from phone…", self.on_remove),
            ("updates", "Check for updates…", self.on_check_updates),
            ("donate", "Buy me a coffee…", self.on_donate),
            ("about", "About Anchor", self.on_about),
        ]:
            action = QAction(text, self)
            action.triggered.connect(lambda _c=False, h=handler: h())
            self.actions[name] = action
        self.menu = QMenu(self)
        self.menu.setAttribute(Qt.WA_TranslucentBackground)
        self.menu.setWindowFlags(self.menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        for group in (("refresh", "backup", "import"), ("remove",), ("updates", "donate", "about")):
            if not self.menu.isEmpty():
                self.menu.addSeparator()
            for name in group:
                self.menu.addAction(self.actions[name])

    def open_menu(self):
        """Opens the menu under its button, right edges lined up."""
        b = self.menu_button
        corner = b.mapToGlobal(b.rect().bottomRight())
        self.menu.popup(QPoint(corner.x() - self.menu.sizeHint().width(), corner.y() + 4))

    def activate_action(self, name, _param=None):
        """Runs a menu action by name ("win.donate" or "donate")."""
        self.actions[name.split(".")[-1]].trigger()

    # ---- Navigation ------------------------------------------------------------------

    def show_page(self, name):
        self.stack.setCurrentWidget(self.pages[name])
        self.actions["remove"].setEnabled(name in ("main", "setup", "foreign", "limit") and self.agent is not None)

    def page_name(self):
        current = self.stack.currentWidget()
        return next(n for n, p in self.pages.items() if p is current)

    def set_subtitle(self, text):
        self.subtitle_label.setText(text)

    def toast(self, text, timeout=3):
        self.toasts.show_text(text, timeout)

    def error_dialog(self, title, body, details=""):
        d = w.AlertDialog(self, title, body)
        if details:
            # Raw adb output can be a long Java stack trace: fold it away and scroll it.
            box = QWidget()
            lay = QVBoxLayout(box)
            lay.setContentsMargins(0, 0, 0, 0)
            toggle = w.button("Details", "link")
            text = QPlainTextEdit(details)
            text.setObjectName("details")
            text.setReadOnly(True)
            text.setMaximumHeight(200)
            text.hide()
            toggle.clicked.connect(lambda: (text.setVisible(not text.isVisible()), d._place()))
            lay.addWidget(toggle, 0, Qt.AlignHCenter)
            lay.addWidget(text)
            d.set_extra_child(box)
        d.add_response("close", "OK")
        d.set_default_response("close")
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
            elif self.page_name() == "main" and not self.working:
                self.refresh_status()

        def fail(_e):
            self.polling = False

        in_background(self.adb.devices, done, fail)
        return True

    def on_device_changed(self, dev):
        if dev is None or dev.state not in ("device", "unauthorized"):
            self.agent = None
            self.set_subtitle("")
            self.show_page("nophone")
            return
        self.set_subtitle(dev.model)
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
                self.set_subtitle(self.model)
            if page == "limit":
                self.limit_page.set_description(self.limit_text(apps) + "<br><br>Or remove Anchor from "
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
        self.setup_button.setEnabled(True)
        self.setup_button.setText("Set up phone" if not any(states) else "Continue setup")

    def on_setup(self, _button):
        if not APK.exists():
            self.error_dialog("Companion app missing",
                              f"Anchor couldn't find {APK.name} next to the app. Reinstall Anchor.")
            return
        agent, token, keys = self.agent, self.keys.token, self.keys
        self.setup_button.setEnabled(False)

        def mark(i, state):
            on_main(lambda: self.step_rows[i].set_visible_child_name(state))

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
            self.setup_button.setEnabled(True)
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
        d = w.AlertDialog(
            self, "The free version works with one phone",
            self.limit_text(other) + f"\n\nIf {name} was factory reset, lost or replaced, you can forget it. "
            f"This computer then gets a new key, so {name} can't be controlled from here any more: "
            "if it still has anchored apps, they stay hidden until it's factory reset.")
        d.add_response("forget", f"Forget {name}")
        d.add_response("ok", "OK")
        d.set_response_appearance("forget", "destructive")
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
        for section in (self.picked_section, self.other_section):
            section.clear()
        self.rows = {}
        self.icons = icons
        self.installed = {a["pkg"] for a in apps}
        labels = {a["pkg"]: a["label"] for a in apps}
        missing = [{"pkg": p, "label": catalog.name_for(p, labels), "system": False}
                   for p in sorted(self.selected) if p not in labels]
        for app in sorted(list(apps) + missing, key=lambda a: a["label"].casefold()):
            row = w.Row(app["label"], app["pkg"], prefix=w.image(w.app_pixmap(icons.get(app["pkg"]), app["label"])),
                        clickable=True)
            # Left to right: Uninstall, schedule, Anchor/Release. Fixed widths line each kind up.
            row.uninstall_button = None
            if not app.get("system") and app["pkg"] in self.installed:
                uninstall = w.button("Uninstall", "row-uninstall", f"Uninstall {app['label']} from your phone",
                                     lambda a=app: self.on_uninstall_app(a))
                row.uninstall_button = uninstall
                slot = uninstall
            else:
                slot = QWidget()  # keeps the columns lined up for apps that can't be uninstalled
            row.uninstall_slot = slot
            self.fit_uninstall(row)
            row.add_suffix(slot)
            sched = w.icon_button("alarm", f"Schedule for {app['label']}",
                                  lambda pkg=app["pkg"]: self.open_app_schedule(pkg), color=theme.FAINT, size=18)
            row.add_suffix(sched)
            row.sched_button = sched
            anchor_button = w.button("Anchor", "row-anchor",
                                     on_click=lambda pkg=app["pkg"]: self.on_anchor_clicked(pkg))
            anchor_button.setFixedWidth(78)
            row.add_suffix(anchor_button)
            row.anchor_button = anchor_button
            # Clicking the row (not its buttons) opens the app's details; it doesn't anchor or release.
            row.activated.connect(lambda a=app: self.open_app_details(a))
            row.pkg, row.label = app["pkg"], app["label"]
            row.sort_key = app["label"].casefold()
            row.search_text = (app["label"] + " " + app["pkg"]).casefold()
            row.sched_on = None
            self.section_for(row.pkg).add(row)
            self.rows[app["pkg"]] = row
        self.populating = False
        self.update_row_notes()
        self.apply_filter()
        self.update_hero()  # section counts

    def fit_uninstall(self, row):
        """Narrow window: Uninstall becomes a trash icon, so the app's name keeps its room."""
        slot, button = row.uninstall_slot, row.uninstall_button
        compact = self.width() < 540
        slot.setFixedWidth(34 if compact else 78)
        if button:
            button.setText("" if compact else "Uninstall")
            button.setIcon(w.symbol_icon("delete", theme.FAINT, 18) if compact else QIcon())
            button.setIconSize(QSize(18, 18))

    def reload_apps(self):
        agent = self.agent

        def done(result):
            if agent is self.agent:
                self.populate_apps(*result)
                self.update_never_allow()

        in_background(agent.apps, done, lambda e: None)

    def section_for(self, pkg):
        return self.picked_section if pkg in self.selected else self.other_section

    def place_rows(self):
        """Moves each row into the section that matches its state."""
        moved = False
        for pkg, row in self.rows.items():
            target = self.section_for(pkg)
            if row not in target.rows:
                (self.other_section if target is self.picked_section else self.picked_section).take(row)
                target.insert_sorted(row)
                moved = True
        if moved:
            self.apply_filter()

    def filter_row(self, row):
        q = self.search.text().strip().casefold()
        return not q or q in row.search_text

    def apply_filter(self, only=None):
        searching = bool(self.search.text().strip())
        for section in (only,) if only else (self.picked_section, self.other_section):
            for row in section.rows:
                row.setVisible(self.filter_row(row))
            section.refresh_empty("No apps match" if searching else section.empty_text)

    def on_search_changed(self, _text):
        if self.search.text().strip():
            for section in (self.picked_section, self.other_section):
                if not section.is_open:
                    section.set_open(True)  # never hide matches in a folded section
        self.apply_filter()

    def on_anchor_clicked(self, pkg):
        """Anchor (hide now) or Release (bring back now) one app."""
        if pkg in self.selected:
            self.selected.discard(pkg)
        else:
            self.selected.add(pkg)
        # Move the row after the click has finished being handled.
        QTimer.singleShot(0, self.place_rows)
        self.update_row_notes()
        self.update_hero()
        self.sync_timer.start()  # several quick clicks are sent together

    def sync_selection(self):
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

    def toast_changes(self, before, after, refused):
        """While anchored, confirms what each button just did on the phone."""
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
        failed = set(st.get("failed", []))
        blocked = set(st.get("blocked", []))
        scheduled_now = st.get("scheduled_now", {})
        removed = st.get("permissions_removed", {})
        for pkg, row in self.rows.items():
            picked = pkg in self.selected
            windows = self.app_schedules(pkg)
            if picked and pkg not in self.installed:
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
            row.set_subtitle(note)  # only repaints when the text changed
            label = "Release" if picked else "Anchor"
            if row.anchor_button.text() != label:
                row.anchor_button.setText(label)
                row.anchor_button.setToolTip(f"{label} {row.label}")
            w.set_kind(row.anchor_button, "row-release" if picked else "row-anchor")
            on = any(x.get("enabled", True) for x in windows)
            if row.sched_on != on:
                row.sched_on = on
                w.set_kind(row.sched_button, "icon-accent" if on else "icon")
                row.sched_button.setIcon(w.symbol_icon("alarm", theme.ACCENT if on else theme.FAINT, 18))

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

        self.hero_button.setVisible(anchored)
        self.pause_button.setVisible(bool(scheduled_now) and not anchored)
        lit = anchored or bool(scheduled_now)
        w.set_flag(self.hero, "anchored", lit)
        self.hero_icon.setPixmap(w.picture("anchor-orb-on.svg" if lit else "anchor-orb-off.svg", 60))
        if anchored:
            if mode == "timer":
                self.hero_title.setText(f"Anchored until {clock(ends)}")
                text = f"{plural(n, 'app')} hidden. They come back by themselves {countdown(ends)}."
            else:
                self.hero_title.setText("Anchored")
                text = f"{plural(n, 'app')} hidden from {self.model} until you release them."
            if on_schedule:
                text += f" {on_schedule} Release all also pauses that until it ends."
        else:
            self.hero_title.setText("On schedule" if scheduled_now else "Not anchored")
            text = on_schedule or ("Tap Anchor on any app below to hide it from your phone right away. "
                                   "Only this computer can bring it back.")
        if self.hero_subtitle.text() != text:
            self.hero_subtitle.setText(text)
        self.hero_button.setEnabled(not self.working)
        self.update_sections(n)

    def update_sections(self, n):
        # The Anchored apps section only shows when something is anchored.
        self.picked_section.setVisible(n > 0)
        self.picked_section.set_title(f"Anchored apps ({n})")
        self.picked_section.set_hint("Hidden from your phone. Tap Release to bring one back.")
        others = sum(1 for p in self.rows if p not in self.selected)
        self.other_section.set_title(f"{'All other apps' if n else 'Your apps'} ({others})")
        self.other_section.set_hint("Tap Anchor to hide an app from your phone right away.")

    def on_hero_clicked(self):
        """Release all: confirmed with the computer's password first."""
        if not self.selected:
            return
        self.hero_button.setEnabled(False)

        def done(result):
            self.hero_button.setEnabled(True)
            if result == "ok":
                self.run_shift(None, unshift=True)
            elif result == "cancelled":
                self.toast("Release all cancelled · your apps stay anchored")
            elif result == "missing":
                self.error_dialog("Can't ask for your password", plat.password_missing_text())
            else:
                self.toast("Password not accepted · your apps stay anchored")

        in_background(lambda: system_password_check(), done, lambda e: done("failed"))

    def run_shift(self, minutes, unshift=False):
        self.sync_timer.stop()
        agent, token = self.agent, self.keys.token
        packages = set(self.selected)
        was_anchored = bool(packages)
        self.working = True
        self.hero_button.setEnabled(False)
        self.pause_button.setEnabled(False)

        def work():
            return agent.unshift(token) if unshift else agent.shift(token, packages, minutes)

        def done(st):
            self.working = False
            self.pause_button.setEnabled(True)
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
            self.pause_button.setEnabled(True)
            self.update_hero()
            self.error_dialog("Couldn't reach the phone" if isinstance(e, ac.AdbError) else "The phone said no",
                              str(e))

        in_background(work, done, fail)

    # ---- App details -------------------------------------------------------------------

    def open_app_details(self, app):
        pkg, label = app["pkg"], app["label"]
        d = w.PanelDialog(self, label, 460, 640)
        top = QVBoxLayout()
        top.setSpacing(6)
        top.addWidget(w.image(w.app_pixmap(self.icons.get(pkg), label, 72)), 0, Qt.AlignHCenter)
        top.addWidget(w.label(label, "nameTitle", wrap=True, align=Qt.AlignCenter))
        top.addWidget(w.label(pkg, "caption", align=Qt.AlignCenter, selectable=True))
        d.body.addLayout(top)
        d.about = w.Group("About")
        d.perms = w.Group("Permissions")
        d.body.addWidget(d.about)
        d.body.addWidget(d.perms)
        d.uninstall = None
        row = self.rows.get(pkg)
        if row and row.uninstall_button:  # apps you installed yourself, like the Uninstall in the list
            d.uninstall = w.button("Uninstall", "pill-danger", f"Uninstall {label} from your phone",
                                   lambda: (d.close_overlay(), self.on_uninstall_app(app)))
            d.body.addWidget(d.uninstall, 0, Qt.AlignHCenter)
        # Until the phone answers: a spinner instead of half-empty cards; then everything at once.
        d.loading = QWidget()
        lay = QVBoxLayout(d.loading)
        lay.setContentsMargins(0, 48, 0, 0)
        lay.setSpacing(12)
        d.spinner = w.Spinner(36)
        lay.addWidget(d.spinner, 0, Qt.AlignHCenter)
        d.loading_text = w.label("Loading…", "dim", wrap=True, align=Qt.AlignCenter)
        lay.addWidget(d.loading_text)
        d.body.addWidget(d.loading)
        for part in (d.about, d.perms, d.uninstall):
            if part:
                part.hide()
        d.body.addStretch(1)
        d.app, d.perm_rows, d.perm_empty = app, {}, None
        d.page_widgets = []
        d.closed.connect(lambda: self.details is d and setattr(self, "details", None))
        d.present(self)
        self.details = d

        agent = self.agent

        def done(info):
            if self.details is d:
                self.fill_app_details(d, info)

        def fail(e):
            if self.details is d:
                d.spinner.hide()
                d.loading_text.setText(f"Couldn't read this app's details\n{e}")

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
        for x in d.page_widgets:
            d.about.remove(x)
        d.page_widgets = []
        d.loading.hide()
        for part in (d.about, d.perms, d.uninstall):
            if part:
                part.show()

        def date(ms):
            return f"{datetime.fromtimestamp(ms / 1000):%d %b %Y}".lstrip("0") if ms else "—"

        for title, value in [
            ("Status", self.status_text(info["pkg"])),
            *([("Screen time today", screen_time(info["usage_today"])),
               ("Screen time, last 7 days", screen_time(info.get("usage_week")))] if "usage_today" in info else []),
            ("Version", info.get("version") or "—"),
            ("Installed", date(info.get("installed"))),
            ("Last updated", date(info.get("updated"))),
            ("Type", "Came with the phone" if info.get("system") else "Installed by you"),
        ]:
            row = w.Row(title, value)
            # A property: the name small and dim, the value as the main text.
            row.title_label.setObjectName("rowSubtitle")
            row.subtitle_label.setObjectName("rowTitle")
            row.subtitle_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            d.about.add(row)
            d.page_widgets.append(row)
        self.fill_permissions(d, info)
        d._place()

    def fill_permissions(self, d, info):
        for row in d.perm_rows.values():
            d.perms.remove(row)
        d.perm_rows = {}
        if d.perm_empty:
            d.perms.remove(d.perm_empty)
            d.perm_empty = None
        blocked = info.get("blocked")
        label = info.get("label", d.app["label"])
        d.perms.set_description(
            f"Permissions are removed while {label} is blocked, and come back when you release it."
            if blocked else "Changes apply on your phone right away. You can still change them in the phone's Settings.")
        if not info.get("permissions"):
            d.perm_empty = w.Row("No permissions to manage", f"{label} doesn't ask for any permissions you grant.")
            d.perms.add(d.perm_empty)
            return
        named = [(friendly(p["name"], p["label"]), p) for p in info["permissions"]]
        for (title, subtitle), perm in sorted(named, key=lambda x: x[0][0].casefold()):
            if blocked and perm.get("had"):
                subtitle = " · ".join(x for x in (subtitle, "comes back when released") if x)
            row = w.SwitchRow(title, subtitle, perm["granted"])
            row.setEnabled(not blocked)
            row.switch.toggled.connect(lambda _on, r=row, name=perm["name"]: self.on_permission_switched(r, d, name))
            d.perms.add(row)
            d.perm_rows[perm["name"]] = row

    def on_permission_switched(self, row, d, permission):
        agent, token, pkg, grant = self.agent, self.keys.token, d.app["pkg"], row.get_active()
        row.setEnabled(False)
        title = row.get_title()

        def done(info):
            self.toast(f"{title}: {'allowed' if grant else 'removed'} for {d.app['label']}")
            if self.details is not d:
                return  # the window was closed or replaced meanwhile
            self.fill_permissions(d, info)

        def fail(e):
            if self.details is not d:
                return
            row.switch.set_quietly(not grant)
            row.setEnabled(True)
            self.toast(f"Couldn't change that permission: {e}")

        in_background(lambda: agent.set_permission(token, pkg, permission, grant), done, fail)

    def on_uninstall_app(self, app):
        d = w.AlertDialog(self, f"Uninstall {app['label']}?", f"{app['label']} and its data are removed from your phone.")
        d.add_response("cancel", "Cancel")
        d.add_response("uninstall", "Uninstall")
        d.set_response_appearance("uninstall", "destructive")
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

    # ---- Schedules -----------------------------------------------------------------------

    def app_schedules(self, pkg):
        return [x for x in self.schedules if pkg in x.get("packages", [])]

    def label_for(self, pkg):
        return self.rows[pkg].label if pkg in self.rows else pkg

    def schedule_summary(self, pkg):
        windows = self.app_schedules(pkg)
        if len(windows) == 1:
            x = windows[0]
            text = f"{days_text(x['days'])} · {hours_text(x['start'], x['end'])}"
            if not x.get("enabled", True):
                text += " · Off"
        else:
            on = sum(1 for x in windows if x.get("enabled", True))
            text = plural(len(windows), "schedule") + ("" if on == len(windows) else f" · {on} on")
        paused = self.status.get("paused", {})
        until = [paused[x["id"]] for x in windows if x["id"] in paused]
        if until:
            text += f" · Paused until {clock(max(until))}"
        return text

    def update_schedules(self):
        self.schedules = [x for x in self.status.get("schedules", []) if x.get("packages")]
        if self.app_dialog:
            self.fill_app_schedule(*self.app_dialog[1:])

    def open_app_schedule(self, pkg):
        label = self.label_for(pkg)
        d = w.AlertDialog(self, f"{label} schedule",
                          f"Hide {label} from your phone at these times, even when you're not anchored. "
                          "Your phone does this by itself; it doesn't need to be plugged in.", width=440)
        holder = QWidget()
        QVBoxLayout(holder).setContentsMargins(0, 0, 0, 0)
        d.set_extra_child(holder)
        d.add_response("close", "Done")
        d.set_default_response("close")
        d.set_close_response("close")
        d.connect("response", lambda *_: setattr(self, "app_dialog", None))
        self.app_dialog = (d, pkg, holder)
        self.fill_app_schedule(pkg, holder)
        d.present(self)

    def fill_app_schedule(self, pkg, holder):
        lay = holder.layout()
        old = getattr(holder, "card", None)
        if old:
            lay.removeWidget(old)
            old.deleteLater()
        card = w.Card()
        holder.card = card
        paused = self.status.get("paused", {})
        hidden_until = self.status.get("scheduled_now", {}).get(pkg)
        if hidden_until:
            now_row = w.Row(f"Hidden right now, until {clock(hidden_until)}",
                            prefix=w.image(w.symbol("lock", theme.LILAC, 20)))
            now_row.window = False
            card.add(now_row)
        for x in self.app_schedules(pkg):
            subtitle = hours_text(x["start"], x["end"])
            if not x.get("enabled", True):
                subtitle += " · Off"
            elif x["id"] in paused:
                subtitle += f" · Paused until {clock(paused[x['id']])}"
            row = w.Row(days_text(x["days"]), subtitle, prefix=w.image(w.symbol("alarm", theme.LILAC, 20)),
                        clickable=True)
            delete = w.icon_button("delete", "Delete", lambda wid=x["id"]: self.delete_window(wid),
                                   color=theme.FAINT, size=18)
            row.add_suffix(delete)
            switch = w.Switch(x.get("enabled", True))
            switch.toggled.connect(lambda on, wid=x["id"]: self.toggle_window(wid, on))
            row.add_suffix(switch)
            row.window, row.switch, row.delete = x, switch, delete
            row.activated.connect(lambda x=x: self.edit_window(pkg, x))
            card.add(row)
        add = w.Row("Add a time", prefix=w.image(w.symbol("add", theme.LILAC, 20)), clickable=True)
        add.window = None
        add.activated.connect(lambda: self.edit_window(pkg, None))
        card.add(add)
        lay.addWidget(card)
        if self.app_dialog and self.app_dialog[0].isVisible():
            QTimer.singleShot(0, self.app_dialog[0]._place)  # the list changed size

    def describe(self, x):
        return f"{self.label_for(x['packages'][0])}: {days_text(x['days'])} {hours_text(x['start'], x['end'])}"

    def toggle_window(self, wid, enabled):
        x = next((s for s in self.schedules if s["id"] == wid), None)
        if x is None or x.get("enabled", True) == enabled:
            return
        self.save_schedules([dict(s, enabled=enabled) if s["id"] == wid else s for s in self.schedules],
                            f"{self.describe(x)} turned {'on' if enabled else 'off'}")

    def delete_window(self, wid):
        x = next(s for s in self.schedules if s["id"] == wid)
        self.save_schedules([s for s in self.schedules if s["id"] != wid], f"{self.describe(x)} deleted")

    def edit_window(self, pkg, window):
        new = window is None
        label = self.label_for(pkg)
        window = window or {"id": uuid.uuid4().hex[:8], "name": label, "enabled": True, "packages": [pkg],
                            "days": [1, 2, 3, 4, 5, 6, 7], "start": "22:30", "end": "07:00"}
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        days = QHBoxLayout()
        days.setSpacing(5)
        day_buttons = []
        for i, name in enumerate(DAY_NAMES, start=1):
            b = QPushButton(name)
            b.setProperty("kind", "day")
            b.setCheckable(True)
            b.setChecked(i in window["days"])
            b.setCursor(Qt.PointingHandCursor)
            days.addWidget(b)
            day_buttons.append(b)
        lay.addLayout(days)

        def to_min(hhmm):
            h, m = hhmm.split(":")
            return int(h) * 60 + int(m)

        start_picker, end_picker = TimePicker(to_min(window["start"])), TimePicker(to_min(window["end"]))
        times = QHBoxLayout()
        times.setSpacing(28)
        times.addStretch(1)
        for caption_text, picker in (("From", start_picker), ("To", end_picker)):
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(w.label(caption_text, "captionHeading", align=Qt.AlignCenter))
            col.addWidget(picker)
            times.addLayout(col)
        times.addStretch(1)
        lay.addLayout(times)
        lay.addWidget(w.label("If the end is earlier than the start, it ends the next morning. "
                              "The same start and end time means all day.", "caption", wrap=True,
                              align=Qt.AlignCenter))

        d = w.AlertDialog(self, f"{'Add a time' if new else 'Edit time'} for {label}", None, width=440)
        d.set_extra_child(content)
        d.add_response("cancel", "Cancel")
        d.add_response("save", "Save")
        d.set_response_appearance("save", "suggested")
        d.set_default_response("save")
        d.set_close_response("cancel")
        d.day_buttons, d.start_picker, d.end_picker = day_buttons, start_picker, end_picker

        def response(_d, rid):
            if rid != "save":
                return
            chosen = [i for i, b in enumerate(day_buttons, start=1) if b.isChecked()]
            if not chosen:
                self.error_dialog("Pick at least one day", "Choose the days this time applies to.")
                return
            start, end = start_picker.minutes(), end_picker.minutes()
            item = dict(window, days=chosen, start=f"{start // 60:02d}:{start % 60:02d}",
                        end=f"{end // 60:02d}:{end % 60:02d}")
            updated = self.schedules + [item] if new else [item if s["id"] == item["id"] else s for s in self.schedules]
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
        d = w.AlertDialog(self, "Backup key",
                          "This key is what lets a computer release your apps. Keep a copy somewhere you "
                          "can't reach on impulse (a password manager, a note in a drawer) in case this "
                          "computer is lost.")
        key = w.label(ac.KeyStore.format(self.keys.token), "keyLabel", wrap=True, align=Qt.AlignCenter,
                      selectable=True)
        d.set_extra_child(key)
        d.add_response("save", "Save as PDF…")
        d.add_response("copy", "Copy")
        d.add_response("close", "Close")
        d.set_default_response("close")
        d.set_close_response("close")

        def response(_d, rid):
            if rid == "copy":
                QApplication.clipboard().setText(ac.KeyStore.format(self.keys.token))
                self.toast("Backup key copied")
            elif rid == "save":
                self.on_save_key_pdf()

        d.connect("response", response)
        d.present(self)

    def on_save_key_pdf(self):
        """A printable page with the key, saved where you choose (Documents by default), so it's kept
        even if Anchor is uninstalled from this computer."""
        from PySide6.QtCore import QStandardPaths
        from PySide6.QtWidgets import QFileDialog

        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        path, _ = QFileDialog.getSaveFileName(self, "Save your backup key", str(Path(docs) / keysheet.FILENAME),
                                              "PDF (*.pdf)")
        if path:
            self.save_key_pdf(path)

    def save_key_pdf(self, path):
        phone = self.model if self.model and self.model != "your phone" else ""
        try:
            write_key_pdf(path, keysheet.page(ac.KeyStore.format(self.keys.token), phone))
        except Exception as e:  # noqa: BLE001 - a folder you can't write to, a full disk…
            self.error_dialog("Couldn't save the backup key", str(e))
            return
        self.toast(f"Backup key saved as {Path(path).name}")

    def on_import(self):
        d = w.AlertDialog(self, "Use a backup key",
                          "Enter the backup key of the computer your phone is paired with. This computer "
                          "will then be able to control the phone. It replaces this computer's current key.")
        entry = QLineEdit()
        entry.setPlaceholderText("XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX")
        entry.setProperty("mono", True)
        entry.returnPressed.connect(lambda: d.emit_response("use"))
        d.set_extra_child(entry)
        d.add_response("cancel", "Cancel")
        d.add_response("use", "Use key")
        d.set_response_appearance("use", "suggested")
        d.set_default_response("use")
        d.set_close_response("cancel")

        def response(_d, rid):
            if rid != "use":
                return
            try:
                self.keys.set(ac.KeyStore.parse(entry.text()))
            except ValueError as e:
                self.error_dialog("That key doesn't look right", str(e))
                return
            self.toast("Backup key saved")
            self.reprobe()

        d.connect("response", response)
        d.present(self)
        entry.setFocus()

    def on_remove(self):
        if not self.agent:
            return
        d = w.AlertDialog(self, f"Remove Anchor from {self.model}?",
                          "Every hidden app comes back and Anchor is uninstalled from the phone. "
                          "You can set it up again any time.")
        d.add_response("cancel", "Cancel")
        d.add_response("remove", "Remove")
        d.set_response_appearance("remove", "destructive")
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

    def on_check_updates(self):
        """Asks GitHub, only now, whether a newer Anchor is out (the only time the app goes online)."""
        def done(result):
            if result == updates.CURRENT:
                d = w.AlertDialog(self, "You're up to date", "This is the newest version of Anchor.")
                d.add_response("close", "OK")
            elif result == updates.AVAILABLE and self.can_update_itself():
                d = w.AlertDialog(self, "A new version of Anchor is available",
                                  "Anchor downloads it from GitHub, installs it over this one and restarts. "
                                  "Your key and settings stay.")
                d.add_response("later", "Not now")
                d.add_response("update", "Update")
                d.set_response_appearance("update", "suggested")
                d.set_default_response("update")
                d.set_close_response("later")
            elif result == updates.AVAILABLE:
                d = w.AlertDialog(self, "A new version of Anchor is available",
                                  "Download it from GitHub and install it over this one. Your key and settings stay.")
                d.add_response("later", "Not now")
                d.add_response("download", "Download")
                d.set_response_appearance("download", "suggested")
                d.set_default_response("download")
                d.set_close_response("later")
            else:
                d = w.AlertDialog(self, "Can't tell which version this is",
                                  "This copy of Anchor wasn't downloaded from GitHub, so there's nothing to compare it with. "
                                  "The newest version is always on the download page.")
                d.add_response("close", "Close")
                d.add_response("download", "Open downloads")
                d.set_close_response("close")
            def response(_d, rid):
                if rid == "download":
                    QDesktopServices.openUrl(QUrl(updates.download_page(UPDATE_CHANNEL)))
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
        """Only Anchor installed by anchor-win.exe can (not a copy run from source)."""
        return plat.installed_by_installer()

    def install_update(self):
        """Downloads the newest anchor-win.exe, then closes Anchor while it installs silently and opens
        the new version. The key and settings in %APPDATA%\\Anchor aren't touched."""
        self.toast("Downloading the new version…", timeout=10)

        def done(installer):
            plat.run_update_installer(installer)
            QApplication.quit()

        def fail(e):
            self.error_dialog("Couldn't update Anchor",
                              "Anchor couldn't download the new version. Check your internet connection "
                              "and try again.", str(e))

        in_background(lambda: updates.download(UPDATE_CHANNEL, "anchor-win.exe"), done, fail)

    def on_donate(self):
        QDesktopServices.openUrl(QUrl(DONATE_URL))

    def on_about(self):
        AboutDialog(self).present(self)


def dark_palette():
    p = QPalette()
    for role, color in [(QPalette.Window, theme.BG), (QPalette.Base, theme.CARD), (QPalette.AlternateBase, theme.CARD),
                        (QPalette.Text, theme.TEXT), (QPalette.WindowText, theme.TEXT),
                        (QPalette.ButtonText, theme.TEXT), (QPalette.Button, theme.CARD),
                        (QPalette.Highlight, theme.VIOLET), (QPalette.HighlightedText, "#FFFFFF"),
                        (QPalette.ToolTipBase, theme.POPOVER), (QPalette.ToolTipText, theme.TEXT),
                        (QPalette.PlaceholderText, "#7D7394"), (QPalette.Link, theme.LILAC)]:
        p.setColor(role, QColor(color))
    return p


def make_app(argv=None):
    plat.set_app_id()
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName("Anchor")
    app.setApplicationDisplayName("Anchor")
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    font = QFont()
    font.setFamilies(theme.FONTS)
    font.setPixelSize(14)
    font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)
    app.setStyleSheet(theme.STYLE)
    app.setWindowIcon(QIcon(w.picture("app.anchor.Desktop.svg", 256)))
    return app


def main():
    app = make_app()
    win = AnchorWindow(app)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

