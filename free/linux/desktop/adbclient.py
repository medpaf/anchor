import base64
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

AGENT_PKG = "app.anchor.agent"
AGENT_ADMIN = f"{AGENT_PKG}/.AdminReceiver"
AGENT_URI = "content://app.anchor.agent.cmd"
AGENT_VERSION = 52
EDITION = "free"

class AdbError(Exception):
    pass

class AgentError(Exception):

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

class SetupError(Exception):

    def __init__(self, title, body, details=""):
        super().__init__(title)
        self.title = title
        self.body = body
        self.details = details.strip()

@dataclass
class Device:
    serial: str
    state: str
    model: str = ""

@dataclass
class Account:
    name: str
    type: str
    package: str = ""

_ACCOUNT_RE = re.compile(r"Account \{name=(.*?), type=([^}]*)\}")
_AUTHENTICATOR_RE = re.compile(r"AuthenticatorDescription \{type=([^}]*)\}, ComponentInfo\{([^/}]+)/")

KNOWN_ACCOUNT_TYPES = {
    "com.google": "Google",
    "com.google.work": "Google (work)",
    "com.osp.app.signin": "Samsung account",
    "com.xiaomi": "Xiaomi account",
}

def find_adb():
    candidates = [shutil.which("adb")]
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(env):
            candidates.append(os.path.join(os.environ[env], "platform-tools", "adb"))
    candidates.append(os.path.expanduser("~/Android/Sdk/platform-tools/adb"))
    for c in candidates:
        if c and os.access(c, os.X_OK):
            return c
    return None

class Adb:
    def __init__(self, path):
        self.path = path

    def run(self, args, serial=None, timeout=30, binary=False):
        cmd = [self.path] + (["-s", serial] if serial else []) + list(args)
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=timeout)
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
            return
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

        if minutes is None:
            return self.call("shift", token=token, packages=sorted(packages))
        return self.call("shift", token=token, packages=sorted(packages), minutes=int(minutes))

    def set_schedules(self, token, schedules):

        return self.call("schedules", token=token, schedules=schedules)

    def install_placeholder(self, package, name=None):
        import placeholder
        label = f"{name} - Blocked" if name else None
        path = placeholder.write_apk(package, label)
        try:
            _, out = self.adb.run(["install", str(path)], serial=self.serial, timeout=120)
        finally:
            path.unlink(missing_ok=True)
        if "Success" not in out:
            raise AdbError(out.strip().splitlines()[-1] if out.strip() else "install failed")
        self.call("check")

    def installed_package(self, package):
        return f"package:{package}" in self.shell(f"pm list packages -u {package}")

    def app_info(self, package):

        return self.call("app_info", pkg=package)

    def set_permission(self, token, package, permission, grant):

        return self.call("set_permission", token=token, pkg=package, permission=permission, grant=bool(grant))

    def end_anchoring(self, token):

        return self.call("end", token=token)

    def uninstall_app(self, token, package):

        return self.call("uninstall", token=token, pkg=package)

    def uninstall_blocked(self, token, package):

        return self.call("uninstall_blocked", token=token, pkg=package)

    def set_install_blocks(self, token, apps):

        return self.call("install_blocks", token=token, apps=apps)

    def allow_background(self):

        self.shell(f"dumpsys deviceidle whitelist +{AGENT_PKG}")
        self.shell(f"cmd appops set {AGENT_PKG} SCHEDULE_EXACT_ALARM allow")
        self.shell(f"cmd appops set {AGENT_PKG} GET_USAGE_STATS allow")

    def unshift(self, token):
        return self.call("unshift", token=token)

    def release(self, token):
        return self.call("release", token=token)

    def apps(self):

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
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            return Path(p).read_text().strip()
        except OSError:
            pass
    return ""

class KeyStore:

    def __init__(self):
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        self.path = Path(base) / "anchor" / "key.json"

    def _read(self):
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {}

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data))
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

    def phone(self):

        p = self._read().get("phone")
        if not p or p.get("machine") != machine_id():
            return None
        return p

    def other_phone(self, st):

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

        p = self.phone()
        if p and p["id"] == device_id:
            data = self._read()
            data.pop("phone", None)
            self._write(data)

    def forget_phone(self):

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
