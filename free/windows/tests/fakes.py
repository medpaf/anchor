"""A fake adb + phone, so the desktop app can be tested without a device.

FakePhone mimics the companion app's command provider (android/.../CommandProvider.java):
same commands, same JSON replies, same error codes. FakeAdb answers the exact adb command lines
that adbclient sends, so the tests go through the real parsing code.
"""

import base64
import hashlib
import io
import json
import re
import struct
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop"))

import adbclient as ac  # noqa: E402


def data_env(path):
    """Environment that points Anchor's data folder at `path` (Linux reads XDG_DATA_HOME, Windows APPDATA)."""
    return {"XDG_DATA_HOME": str(path), "APPDATA": str(path)}

# Smallest valid PNG (1x1 transparent pixel), used as an app icon.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")

DEFAULT_APPS = [
    ("com.instagram.android", "Instagram"),
    ("com.google.android.youtube", "YouTube"),
    ("com.reddit.frontpage", "Reddit"),
    ("com.google.android.apps.maps", "Maps"),
    ("com.google.android.dialer", "Phone"),
]


class FakePhone:
    PROTECTED = {"com.google.android.dialer"}  # Android refuses to suspend these
    SYSTEM = {"com.google.android.youtube", "com.google.android.apps.maps", "com.google.android.dialer"}

    def __init__(self, apps=DEFAULT_APPS, version=ac.AGENT_VERSION, model="Google Pixel 8",
                 device_id="a1b2c3d4e5f60718"):
        self.apps = dict(apps)
        self.device_id = device_id
        self.version = version
        self.model = model
        self.installed = False
        self.owner = False
        self.token_hash = None
        self.selected = set()
        self.blocked = set()
        self.failed = set()
        self.shifted = False  # manual shift
        self.until = 0  # timed shift end (ms)
        self.schedules = []
        self.active_windows = {}  # tests set {schedule id: window end ms} to simulate "on right now"
        self.paused = {}  # schedule id -> paused until (ms)
        self.background_allowed = False
        self.install_blocks = []  # [{pkg, name}]
        self.install_blocks_set = False
        self.kept = set()  # on the list but already installed when added
        self.placeholders = set()  # never-allowed packages held by Anchor's placeholder app
        self.placeholder_installs = []  # what the computer pushed, for tests to inspect
        self.refuse_placeholders = False  # simulate a phone that won't take USB installs
        self.granted = {}  # pkg -> runtime permissions the user granted
        self.uses = {"com.instagram.android": ["android.permission.CAMERA", "android.permission.RECORD_AUDIO",
                                               "android.permission.POST_NOTIFICATIONS"]}  # pkg -> permissions it asks for
        self.revoked = {}  # pkg -> permissions Anchor took away while the app is blocked
        self.dpm_output = None  # set to simulate a `dpm set-device-owner` failure
        self.install_output = None  # set to simulate an `adb install` failure
        self.accounts = []  # (name, type, owning package) signed in on the phone
        self.commands = []

    # ---- helpers for tests ----
    def ready(self, token):
        """Puts the phone in the fully set-up state, paired with `token`."""
        self.installed = self.owner = True
        self.token_hash = self._hash(token)
        self.install_blocks_set = True  # an existing setup; tests of the defaults turn this off
        return self

    @staticmethod
    def _hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def now():
        return int(time.time() * 1000)

    def mode(self):
        if self.shifted:
            return "manual"
        if self.until > self.now():
            return "timer"
        if self.until:  # a timer that ran out: its apps come back and leave the list
            self.until, self.selected = 0, set()
        return None

    def ends(self):
        return self.until if self.mode() == "timer" else 0

    def live_paused(self):
        return {i: t for i, t in self.paused.items() if t > self.now()}

    def scheduled_now(self):
        """Same rule as Core.scheduledNow: apps of enabled, active, unpaused schedules."""
        out = {}
        for sch in self.schedules:
            end = self.active_windows.get(sch["id"])
            if not sch.get("enabled", True) or not end or sch["id"] in self.live_paused():
                continue
            for pkg in sch.get("packages", []):
                out[pkg] = max(out.get(pkg, 0), end)
        return out

    def caught(self):
        """Same rule as InstallBlocks.caught: installed, never allowed, and not kept."""
        out = set()
        for app in self.install_blocks:
            if app["pkg"] in self.apps:
                if app["pkg"] not in self.kept:
                    out.add(app["pkg"])
            else:
                self.kept.discard(app["pkg"])
        return out

    def install(self, pkg, label):
        """Simulates installing an app (the phone then notices and re-applies). Returns False when
        Android refuses because Anchor's placeholder holds the name."""
        if pkg in self.placeholders:
            return False
        self.apps[pkg] = label
        self._apply()
        return True

    def missing(self):
        return sorted(a["pkg"] for a in self.install_blocks
                      if a["pkg"] not in self.apps and a["pkg"] not in self.placeholders)

    def sync_placeholders(self):
        """Like InstallBlocks.syncPlaceholders: released apps lose their placeholder."""
        listed = {a["pkg"] for a in self.install_blocks}
        self.placeholders &= listed

    def _apply(self):
        want = (set(self.selected) if self.mode() else set()) | set(self.scheduled_now()) | self.caught()
        want &= set(self.apps)
        self.failed = want & self.PROTECTED
        self.blocked = want - self.failed
        # Same rule as Permissions.sync: blocked apps lose their permissions, released ones get them back.
        for pkg in self.blocked:
            if self.granted.get(pkg):
                self.revoked.setdefault(pkg, set()).update(self.granted.pop(pkg))
        for pkg in list(self.revoked):
            if pkg not in self.blocked:
                self.granted.setdefault(pkg, set()).update(self.revoked.pop(pkg))

    def _status(self, token):
        return {
            "version": self.version, "model": self.model, "android": "14", "device_id": self.device_id,
            "owner": self.owner, "paired": self.token_hash is not None,
            "authorized": self.token_hash is not None and self._hash(token) == self.token_hash,
            "shifted": self.mode() is not None, "shifted_at": 0,
            "now": self.now(), "mode": self.mode(), "ends": self.ends(),
            "scheduled_now": self.scheduled_now(), "paused": self.live_paused(),
            "schedules": self.schedules, "exact_alarms": True,
            "install_blocks": self.install_blocks, "install_blocks_set": self.install_blocks_set,
            "install_kept": sorted(self.kept), "install_caught": sorted(self.caught()),
            "install_placeholders": sorted(self.placeholders), "install_missing": self.missing(),
            "permissions_removed": {p: len(v) for p, v in self.revoked.items() if v},
            "selected": sorted(self.selected), "blocked": sorted(self.blocked), "failed": sorted(self.failed),
        }

    # ---- the provider ----
    def call(self, method, payload):
        self.commands.append(method)
        token = payload.get("token", "")

        def err(code, msg):
            return {"ok": False, "error": code, "message": msg}

        def need_auth():
            if not self.owner:
                return err("not_owner", "Anchor isn't the device owner yet")
            if self.token_hash is None or self._hash(token) != self.token_hash:
                return err("bad_key", "This computer's key doesn't match the phone")
            return None

        if method == "status":
            res = self._status(token)
        elif method == "check":
            if not self.owner:
                return err("not_owner", "Anchor isn't the device owner yet")
            self._apply()
            res = self._status(token)
        elif method in ("app_info", "set_permission"):
            pkg = payload.get("pkg")
            if pkg not in self.apps:
                return err("bad_request", f"{pkg} isn't installed")
            if method == "set_permission":
                e = need_auth()
                if e:
                    return e
                if pkg in self.blocked:
                    return err("bad_request", "Its permissions are removed while it's blocked. Release it first.")
                perm = payload["permission"]
                if perm not in self.uses.get(pkg, []):
                    return err("bad_request", f"{pkg} doesn't use {perm}")
                have = self.granted.setdefault(pkg, set())
                (have.add if payload["grant"] else have.discard)(perm)
            labels = {"android.permission.CAMERA": "take pictures and videos",
                      "android.permission.RECORD_AUDIO": "record audio",
                      "android.permission.POST_NOTIFICATIONS": "show notifications"}
            res = {"pkg": pkg, "label": self.apps[pkg], "version": "1.2.3", "version_code": 123,
                   "installed": 1_700_000_000_000, "updated": 1_760_000_000_000,
                   "system": pkg in self.SYSTEM, "target_sdk": 35, "blocked": pkg in self.blocked,
                   "usage_today": 25 * 60_000, "usage_week": 190 * 60_000,
                   "permissions": [{"name": p, "label": labels.get(p, p), "granted": p in self.granted.get(pkg, set()),
                                    "locked": pkg in self.blocked, "had": p in self.revoked.get(pkg, set())}
                                   for p in self.uses.get(pkg, [])]}
        elif method in ("end", "uninstall"):
            e = need_auth()
            if e:
                return e
            if method == "end":
                self.shifted, self.until, self.selected = False, 0, set()
            else:
                pkg = payload.get("pkg")
                if pkg not in self.apps or pkg in self.SYSTEM:
                    return err("bad_request", "System apps can't be uninstalled")
                del self.apps[pkg]
            self._apply()
            res = self._status(token)
        elif method == "uninstall_blocked":
            e = need_auth()
            if e:
                return e
            if payload.get("pkg") not in self.caught():
                return err("bad_request", "isn't a blocked app that's installed")
            del self.apps[payload["pkg"]]
            self._apply()
            res = self._status(token)
        elif method == "pair":
            if not self.owner:
                return err("not_owner", "Anchor isn't the device owner yet")
            if self.token_hash is not None:
                return err("already_paired", "This phone is already paired with a computer")
            self.token_hash = self._hash(token)
            res = self._status(token)
        elif method in ("select", "shift", "unshift", "release", "schedules", "install_blocks"):
            e = need_auth()
            if e:
                return e
            if method == "install_blocks":
                apps = payload.get("apps")
                if not isinstance(apps, list) or any(
                        not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+", str(a.get("pkg", "")))
                        for a in apps):
                    return err("bad_request", "Not a package name")
                before = {a["pkg"] for a in self.install_blocks}
                for a in apps:
                    if a["pkg"] not in before and a["pkg"] in self.apps:
                        self.kept.add(a["pkg"])
                self.kept &= {a["pkg"] for a in apps}
                self.install_blocks = sorted(apps, key=lambda a: a["pkg"])
                self.install_blocks_set = True
                self.sync_placeholders()
            if method == "schedules":
                bad = self._check_schedules(payload.get("schedules"))
                if bad:
                    return err("bad_request", bad)
                self.schedules = payload["schedules"]
            if "packages" in payload:
                self.selected = set(payload["packages"])
            if method == "shift":
                if "minutes" in payload:
                    if not 1 <= payload["minutes"] <= 7 * 24 * 60:
                        return err("bad_request", "You can anchor for 1 minute to 7 days")
                    self.shifted, self.until = False, self.now() + payload["minutes"] * 60_000
                else:
                    self.shifted, self.until = True, 0
            if method in ("unshift", "release"):
                self.shifted, self.until, self.selected = False, 0, set()
                for sch in self.schedules:
                    end = self.active_windows.get(sch["id"])
                    if sch.get("enabled", True) and end:
                        self.paused[sch["id"]] = end
            if method == "release":
                self.schedules, self.paused = [], {}
                self.install_blocks, self.kept, self.placeholders = [], set(), set()
            self._apply()
            if method == "release":
                self.token_hash = None
                self.owner = False
            res = self._status(token)
        else:
            return err("unknown_method", "Unknown command: " + method)
        res["ok"] = True
        return res

    @staticmethod
    def _check_schedules(schedules):
        """Same rules as Core.parseSchedules on the phone."""
        if not isinstance(schedules, list):
            return "schedules must be a list"
        for sch in schedules:
            if not isinstance(sch.get("id"), str) or not sch.get("days"):
                return "each schedule needs an id and days"
            if not isinstance(sch.get("packages", []), list):
                return "packages must be a list"
            if any(not 1 <= d <= 7 for d in sch["days"]):
                return "Days must be 1 (Mon) to 7 (Sun)"
            for key in ("start", "end"):
                if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(sch.get(key, ""))):
                    return f"Bad time: {sch.get(key)}"
        return None

    def apps_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("apps.json", json.dumps({"apps": [
                {"pkg": p, "label": l, "system": p in self.SYSTEM} for p, l in self.apps.items()]}))
            for p in self.apps:
                z.writestr(f"icons/{p}.png", PNG)
        return buf.getvalue()


class FakeAdb(ac.Adb):
    """Stands in for the adb binary. `devices` is the list `adb devices -l` reports."""

    def __init__(self, phone=None, devices=None):
        super().__init__("/fake/adb")
        self.phone = phone or FakePhone()
        self.device_list = devices if devices is not None else [("SERIAL1", "device", "Pixel_8")]
        self.log = []

    def run(self, args, serial=None, timeout=30, binary=False):
        self.log.append(list(args))
        ph = self.phone
        if args[:2] == ["devices", "-l"]:
            lines = ["List of devices attached"] + [
                f"{s}\t{st} product:x model:{m} device:y transport_id:1" for s, st, m in self.device_list]
            return 0, "\n".join(lines) + "\n"
        if args[0] == "install" and "anchor-placeholder-" in args[-1]:
            pkg = placeholder_package(args[-1])
            if ph.refuse_placeholders:
                return 1, "Failure [INSTALL_FAILED_USER_RESTRICTED: Install canceled by user]"
            if pkg in ph.apps or pkg in ph.placeholders:
                return 1, f"Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package {pkg} signatures do not match]"
            ph.placeholders.add(pkg)
            ph.placeholder_installs.append(pkg)
            ph._apply()
            return 0, "Performing Streamed Install\nSuccess\n"
        if args[0] == "install":
            if ph.install_output:
                return 1, ph.install_output
            ph.installed = True
            ph.version = ac.AGENT_VERSION
            return 0, "Performing Streamed Install\nSuccess\n"
        if args[0] == "uninstall":
            if ph.owner:
                return 1, "Failure [DELETE_FAILED_DEVICE_POLICY_MANAGER]"
            ph.installed = False
            return 0, "Success\n"
        if args[0] == "exec-out":
            if not ph.installed:
                return 0, b"Error while accessing provider", ""
            return 0, ph.apps_zip(), ""
        if args[0] == "shell":
            return 0, self._shell(args[1])
        raise AssertionError(f"unexpected adb call: {args}")

    def _shell(self, cmd):
        ph = self.phone
        if cmd.startswith("pm list packages -u "):
            pkg = cmd.split()[-1]
            return f"package:{pkg}\n" if pkg in ph.apps or pkg in ph.placeholders else ""
        if cmd.startswith("pm path "):
            return "package:/data/app/base.apk\n" if ph.installed else ""
        if cmd.startswith("dumpsys deviceidle whitelist +") or cmd.startswith("cmd appops set"):
            ph.background_allowed = True
            return "Added: app.anchor.agent\n" if "deviceidle" in cmd else ""
        if cmd == "dumpsys account":
            return dumpsys_account(ph.accounts)
        if cmd.startswith("dpm set-device-owner"):
            if ph.accounts:
                return ("Exception occurred while executing 'set-device-owner':\n"
                        "java.lang.IllegalStateException: Not allowed to set the device owner because there "
                        "are already some accounts on the device\n"
                        "\tat com.android.server.devicepolicy.DevicePolicyManagerService.enforceCanSetDeviceOwnerLocked"
                        "(DevicePolicyManagerService.java:11187)\n")
            if ph.dpm_output:
                return ph.dpm_output
            ph.owner = True
            return ("Success: Device owner set to package ComponentInfo{app.anchor.agent/.AdminReceiver}\n"
                    "Active admin set to component {app.anchor.agent/.AdminReceiver}\n")
        m = re.match(r"content call --uri \S+ --method (\w+)(?: --arg (\S+))?$", cmd)
        if m:
            if not ph.installed:
                return "Error while accessing provider:app.anchor.agent.cmd\njava.lang.IllegalArgumentException: Unknown authority"
            payload = json.loads(base64.b64decode(m.group(2))) if m.group(2) else {}
            return "Result: Bundle[{json=%s}]\n" % json.dumps(ph.call(m.group(1), payload), separators=(",", ":"))
        raise AssertionError(f"unexpected shell command: {cmd}")


def dumpsys_account(accounts):
    """`adb shell dumpsys account` output in the format Android 14-16 prints."""
    lines = ["User UserInfo{0:Owner:4c13}:", f"  Accounts: {len(accounts)}"]
    lines += [f"    Account {{name={n}, type={t}}}" for n, t, _ in accounts]
    lines += ["  ", "  AccountId, Action_Type, timestamp, UID, TableName, Key", "  Accounts History",
              "  169,action_authenticator_remove,2026-08-26 13:10:56,1000,accounts,17", "",
              "  RegisteredServicesCache: 3 services"]
    owners = {t: p for _, t, p in accounts}
    owners.setdefault("com.google", "com.google.android.gms")
    owners.setdefault("com.whatsapp", "com.whatsapp")
    lines += [f"    ServiceInfo: AuthenticatorDescription {{type={t}}}, ComponentInfo{{{p}/{p}.AuthService}}, "
              f"uid 10050, lastUpdateTime -1" for t, p in owners.items()]
    return "\n".join(lines) + "\n"


def placeholder_package(apk_path):
    """Reads the package name out of a placeholder APK built by desktop/placeholder.py."""
    import placeholder
    with zipfile.ZipFile(apk_path) as z:
        axml = z.read("AndroidManifest.xml")
        assert {"META-INF/MANIFEST.MF", "META-INF/ANCHOR.SF", "META-INF/ANCHOR.RSA"} <= set(z.namelist())
    header = struct.unpack_from("<HHI", axml, 0)[1]
    size = struct.unpack_from("<I", axml, header + 4)[0]
    strings, _, _ = placeholder._parse_pool(axml[header:header + size])
    names = [s for s in strings if re.fullmatch(r"[A-Za-z][\w]*(\.[A-Za-z][\w]*)+", s)
             and s not in ("app.anchor.placeholder",)]
    assert len(names) == 1, names
    return names[0]
