"""Talks to the Anchor agent on an Android phone over adb (USB)."""

import base64
import io
import json
import os
import re
import secrets
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

import platform_support as plat

AGENT_PKG = "app.anchor.agent"
AGENT_ADMIN = f"{AGENT_PKG}/.AdminReceiver"
AGENT_URI = "content://app.anchor.agent.cmd"
AGENT_VERSION = 40  # must match CommandProvider.VERSION in the bundled APK
EDITION = "free"  # the phone app is the same for free and Pro; it shows this edition's name


class AdbError(Exception):
    """adb failed or the phone went away."""


class AgentError(Exception):
    """The agent on the phone refused a command."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class SetupError(Exception):
    """A setup step failed; carries a friendly explanation and the raw output."""

    def __init__(self, title, body, details=""):
        super().__init__(title)
        self.title = title
        self.body = body
        self.details = details.strip()


@dataclass
class Device:
    serial: str
    state: str  # "device", "unauthorized", "offline", ...
    model: str = ""


@dataclass
class Account:
    name: str
    type: str
    package: str = ""


# `dumpsys account` lines: "Account {name=me@x.com, type=com.google}" and
# "ServiceInfo: AuthenticatorDescription {type=com.google}, ComponentInfo{com.google.android.gms/...}"
_ACCOUNT_RE = re.compile(r"Account \{name=(.*?), type=([^}]*)\}")
_AUTHENTICATOR_RE = re.compile(r"AuthenticatorDescription \{type=([^}]*)\}, ComponentInfo\{([^/}]+)/")

# Account types whose owning app has an unhelpful name (e.g. "Google Play services").
KNOWN_ACCOUNT_TYPES = {
    "com.google": "Google",
    "com.google.work": "Google (work)",
    "com.osp.app.signin": "Samsung account",
    "com.xiaomi": "Xiaomi account",
}


def find_adb():
    return plat.find_adb()


class Adb:
    def __init__(self, path):
        self.path = path

    def run(self, args, serial=None, timeout=30, binary=False):
        cmd = [self.path] + (["-s", serial] if serial else []) + list(args)
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=plat.NO_WINDOW,
                               env=plat.adb_env())
        except subprocess.TimeoutExpired:
            raise AdbError("The phone didn't respond in time. Check the USB cable.")
        if binary:
            return p.returncode, p.stdout, p.stderr.decode(errors="replace")
        return p.returncode, (p.stdout + p.stderr).decode(errors="replace")

    def devices(self):
        _, out = self.run(["devices", "-l"], timeout=10)
        found = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("*") or line.startswith("List of devices"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            info = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
            found.append(Device(parts[0], parts[1], info.get("model", "").replace("_", " ")))
        return found


class Agent:
    """The Anchor companion app on one connected phone."""

    def __init__(self, adb, serial):
        self.adb = adb
        self.serial = serial

    def shell(self, command, timeout=30):
        _, out = self.adb.run(["shell", command], serial=self.serial, timeout=timeout)
        return out

    def installed(self):
        return "package:" in self.shell(f"pm path {AGENT_PKG}")

    def install(self, apk):
        _, out = self.adb.run(["install", "-r", str(apk)], serial=self.serial, timeout=180)
        if "Success" in out:
            return
        if "INSTALL_FAILED_USER_RESTRICTED" in out:
            raise SetupError(
                "The phone blocked the install",
                "Your phone doesn't allow installing apps over USB yet. In Developer options, turn on "
                "“Install via USB” (on Xiaomi, Redmi and POCO phones this needs a Mi account and a SIM card), "
                "then try again. Also watch the phone screen: some phones ask you to confirm the install.",
                out)
        if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in out:
            raise SetupError(
                "A different Anchor is already installed",
                "The phone has a copy of Anchor signed with another key. Remove it from the phone "
                "(Settings → Apps → Anchor → Uninstall) and try again.",
                out)
        raise SetupError("Couldn't install Anchor on the phone",
                         "adb reported an error while installing the companion app.", out)

    def set_device_owner(self):
        out = self.shell(f"dpm set-device-owner {AGENT_ADMIN}")
        if "Success" in out:
            return
        current = re.search(r"but device owner \((.*?)\) is already set", out)
        if current and current.group(1).startswith(AGENT_PKG + "/"):
            return  # an earlier attempt already made Anchor the device owner
        low = out.lower()
        if "account" in low:
            raise SetupError("Remove the accounts from your phone first", self._accounts_help(), out)
        if "several users" in low or "multiple users" in low:
            raise SetupError(
                "Remove extra users and work profiles",
                "This phone has a second user, guest, work profile or “Second space”/“Dual apps”. "
                "Android only allows a device owner on a phone with a single user. Remove the extra ones "
                "in Settings → System → Multiple users (and any work profile), then try again.",
                out)
        if "already set" in low or "already provisioned" in low or "device owner is already" in low:
            raise SetupError(
                "Another app already manages this phone",
                "This phone already has a device owner (for example a work or school app). "
                "Anchor can't be set up while another manager is in control.",
                out)
        if "manage_device_admins" in low or "neither user 2000" in low:
            raise SetupError(
                "One more developer switch is needed",
                "On Xiaomi, Redmi and POCO phones, open Developer options and also turn on "
                "“USB debugging (Security settings)”, then try again.",
                out)
        raise SetupError("Couldn't make Anchor the device owner",
                         "Android refused the request. The message from the phone is below.", out)

    def accounts(self):
        """Accounts signed in on the phone, as Account(name, type, package) — package is the app
        that owns that kind of account (from `dumpsys account`)."""
        out = self.shell("dumpsys account")
        owners = dict(_AUTHENTICATOR_RE.findall(out))
        found = []
        for name, kind in _ACCOUNT_RE.findall(out):
            acc = Account(name, kind, owners.get(kind, ""))
            if acc not in found:
                found.append(acc)
        return found

    def _accounts_help(self):
        intro = "Android only lets an app become device owner on a phone with no accounts signed in. "
        outro = ("You can add everything back as soon as setup is done; your data stays on the phone "
                 "and in the cloud.")
        try:
            accounts = self.accounts()
        except AdbError:
            accounts = []
        if not accounts:
            return (intro + "Open Settings → Passwords & accounts (or Accounts) and remove every "
                    "account, including Google and app accounts like WhatsApp. Then click Continue setup. "
                    + outro)
        try:
            labels = {a["pkg"]: a["label"] for a in self.apps()[0]}
        except (AdbError, KeyError, ValueError):
            labels = {}
        lines = []
        for acc in accounts:
            app = KNOWN_ACCOUNT_TYPES.get(acc.type) or labels.get(acc.package) or acc.package or acc.type
            lines.append(f"•  {app}: {acc.name}")
        one = len(accounts) == 1
        count = "This account is" if one else f"These {len(accounts)} accounts are"
        return (intro + f"{count} still on your phone:\n\n" + "\n".join(lines) + "\n\n"
                f"Remove {'it' if one else 'them'} in Settings → Passwords & accounts. If an app's account isn't listed "
                "there, sign out inside that app, or uninstall the app for a moment. Then click "
                "Continue setup. " + outro)

    def uninstall(self):
        self.adb.run(["uninstall", AGENT_PKG], serial=self.serial, timeout=60)

    # ---- Commands -----------------------------------------------------------------------

    def call(self, method, **payload):
        cmd = f"content call --uri {AGENT_URI} --method {method}"
        if payload:
            arg = base64.b64encode(json.dumps(payload).encode()).decode()
            cmd += f" --arg {arg}"
        out = self.shell(cmd)
        m = re.search(r"json=(\{.*\})\}\]", out, re.S)
        if not m:
            if "Could not find provider" in out or "Unknown authority" in out:
                raise AdbError("Anchor isn't installed on this phone.")
            raise AdbError(out.strip() or "No answer from the phone.")
        res = json.loads(m.group(1))
        if not res.get("ok"):
            raise AgentError(res.get("error", "error"), res.get("message", "The phone refused the command."))
        return res

    def status(self, token):
        return self.call("status", token=token, edition=EDITION)

    def pair(self, token):
        return self.call("pair", token=token)

    def select(self, token, packages):
        return self.call("select", token=token, packages=sorted(packages))

    def shift(self, token, packages, minutes=None):
        """Anchors until released, or for `minutes` when given (the apps come back by themselves)."""
        if minutes is None:
            return self.call("shift", token=token, packages=sorted(packages))
        return self.call("shift", token=token, packages=sorted(packages), minutes=int(minutes))

    def set_schedules(self, token, schedules):
        """schedules: [{id, name, enabled, days: [1..7 = Mon..Sun], start: "22:30", end: "07:00"}]"""
        return self.call("schedules", token=token, schedules=schedules)

    def install_placeholder(self, package):
        """Installs Anchor's placeholder under `package`, so the real app can't be installed."""
        import placeholder
        path = placeholder.write_apk(package)
        try:
            _, out = self.adb.run(["install", str(path)], serial=self.serial, timeout=120)
        finally:
            path.unlink(missing_ok=True)
        if "Success" not in out:
            raise AdbError(out.strip().splitlines()[-1] if out.strip() else "install failed")
        self.call("check")  # hide and lock it right away

    def installed_package(self, package):
        return f"package:{package}" in self.shell(f"pm list packages -u {package}")

    def app_info(self, package):
        """Version, dates and permissions of one app: {label, version, installed, updated, system,
        blocked, permissions: [{name, label, granted, locked, had}]}."""
        return self.call("app_info", pkg=package)

    def set_permission(self, token, package, permission, grant):
        """Grants or removes one permission. Returns the app's updated info."""
        return self.call("set_permission", token=token, pkg=package, permission=permission, grant=bool(grant))

    def end_anchoring(self, token):
        """Stops anchoring (used when the last anchored app is released). Schedules keep running."""
        return self.call("end", token=token)

    def uninstall_app(self, token, package):
        """Uninstalls an app the user picked (not system apps). Its data on the phone is deleted."""
        return self.call("uninstall", token=token, pkg=package)

    def remove_system_app(self, package):
        """Removes an app that came with the phone for the phone's user. Only the USB connection can:
        the phone app's own uninstall would only take away its updates. Android keeps a copy, which
        restore_system_app brings back."""
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+", package):
            raise ValueError(f"Not a package name: {package}")
        out = self.shell(f"pm uninstall --user 0 {package}").strip()
        if "Success" not in out:
            if "BLOCKED" in out:
                raise AdbError("Anchor keeps anchored apps from being removed. Release it first, then remove it.")
            raise AdbError(out or "The phone didn't remove it.")

    def restore_system_app(self, token, package):
        """Brings back an app that came with the phone and was uninstalled (only the computer can)."""
        return self.call("restore_system_app", token=token, pkg=package)

    def uninstall_blocked(self, token, package):
        """Removes a never-allowed app that got installed (only when the user asks)."""
        return self.call("uninstall_blocked", token=token, pkg=package)

    def set_install_blocks(self, token, apps):
        """The full 'Never allow' list: [{pkg, name}]. Apps on it can't be used until released."""
        return self.call("install_blocks", token=token, apps=apps)

    def allow_background(self):
        """Lets the phone app wake up on time for timers and schedules (no battery optimisation,
        and permission for exact alarms) and read screen time for app details. Safe to repeat."""
        self.shell(f"dumpsys deviceidle whitelist +{AGENT_PKG}")
        self.shell(f"cmd appops set {AGENT_PKG} SCHEDULE_EXACT_ALARM allow")
        self.shell(f"cmd appops set {AGENT_PKG} GET_USAGE_STATS allow")  # screen time in app details

    def unshift(self, token):
        return self.call("unshift", token=token)

    def release(self, token):
        return self.call("release", token=token)

    def apps(self):
        """Returns (apps, icons): apps is a list of {pkg, label, system}; icons maps pkg -> PNG bytes."""
        code, data, err = self.adb.run(
            ["exec-out", f"content read --uri {AGENT_URI}/apps.zip"],
            serial=self.serial, timeout=60, binary=True)
        if not data.startswith(b"PK"):
            raise AdbError((data[:300].decode(errors="replace") + err).strip() or "Couldn't read the app list.")
        icons = {}
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            apps = json.loads(z.read("apps.json"))["apps"]
            for name in z.namelist():
                if name.startswith("icons/") and name.endswith(".png"):
                    icons[name[6:-4]] = z.read(name)
        apps.sort(key=lambda a: a["label"].casefold())
        return apps, icons


def machine_id():
    return plat.machine_id()


class KeyStore:
    """The secret that lets this computer release a phone. Kept in key.json in the data folder
    (Windows: %APPDATA%\\Anchor).

    The free version also keeps the one phone this computer works with, next to the key."""

    def __init__(self):
        self.path = plat.data_dir() / "key.json"

    def _read(self):
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {}

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data))
        if not plat.WINDOWS:  # %APPDATA% is already private to the user
            os.chmod(self.path, 0o600)

    @property
    def token(self):
        data = self._read()
        if "token" in data:
            return data["token"]
        return self.set(secrets.token_hex(16))

    def set(self, token):
        data = self._read()
        data["token"] = token
        self._write(data)
        return token

    # ---- Free version: one phone per computer ----------------------------------------------

    def phone(self):
        """The phone this computer is kept for, or None. A key copied from another computer has none."""
        p = self._read().get("phone")
        if not p or p.get("machine") != machine_id():
            return None
        return p

    def other_phone(self, st):
        """The phone this computer is kept for, when the status `st` comes from a different one."""
        p, device_id = self.phone(), st.get("device_id")
        if p and device_id and p["id"] != device_id:
            return p
        return None

    def claim(self, st):
        if st.get("device_id"):
            data = self._read()
            data["phone"] = {"id": st["device_id"], "model": st.get("model", ""), "machine": machine_id()}
            self._write(data)

    def free_slot(self, device_id):
        """Anchor was removed from that phone: another phone can be set up."""
        p = self.phone()
        if p and p["id"] == device_id:
            data = self._read()
            data.pop("phone", None)
            self._write(data)

    def forget_phone(self):
        """For a phone that was reset or lost. A new key, so the old phone can't be switched back in."""
        data = self._read()
        data.pop("phone", None)
        data["token"] = secrets.token_hex(16)
        self._write(data)


    @staticmethod
    def format(token):
        t = token.upper()
        return "-".join(t[i:i + 4] for i in range(0, len(t), 4))

    @staticmethod
    def parse(text):
        t = re.sub(r"[^0-9a-fA-F]", "", text).lower()
        if len(t) != 32:
            raise ValueError("A backup key has 32 letters and digits (0–9, A–F).")
        return t
