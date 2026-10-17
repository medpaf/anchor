"""Everything that differs between Windows and Linux: folders, finding adb, the password prompt."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

WINDOWS = sys.platform == "win32"
HERE = Path(__file__).resolve().parent

# adb.exe and friends open a console window on Windows unless told not to.
NO_WINDOW = subprocess.CREATE_NO_WINDOW if WINDOWS else 0


def data_dir():
    """Where Anchor keeps its key and settings.

    Windows: %APPDATA%\\Anchor. Linux: ~/.local/share/anchor, the same folder as the GTK app, so
    both apps on one computer share the key."""
    if WINDOWS:
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Anchor"
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "anchor"


def adb_candidates():
    exe = "adb.exe" if WINDOWS else "adb"
    bundled = HERE / "platform-tools" / exe  # shipped with the Windows installer
    found = [str(bundled) if bundled.is_file() else None, shutil.which("adb")]
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(env):
            found.append(os.path.join(os.environ[env], "platform-tools", exe))
    if WINDOWS:
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        found.append(os.path.join(local, "Android", "Sdk", "platform-tools", exe))
    else:
        found.append(os.path.expanduser("~/Android/Sdk/platform-tools/adb"))
    return [c for c in found if c]


def adb_env():
    """adb's environment, without mDNS (its search for phones on the network for wireless debugging).
    Anchor only uses USB, and mDNS makes adb listen on every network connection, which is what brings
    up the Windows Firewall prompt. Without it adb only listens on 127.0.0.1, which the firewall allows."""
    env = dict(os.environ)
    env["ADB_MDNS"] = "0"
    return env


def find_adb():
    for c in adb_candidates():
        if os.access(c, os.X_OK):
            return c
    return None


def adb_install_hint():
    if WINDOWS:
        return ("Anchor uses adb to talk to your phone, and it should come with Anchor. Reinstall "
                "Anchor, or put Google's <b>platform-tools</b> folder next to the app.")
    return ("Anchor uses adb to talk to your phone. Install it, then reopen Anchor:\n\n"
            "<tt>sudo apt install adb</tt>")


def machine_id():
    """An ID for this computer that survives reinstalls (Windows: MachineGuid)."""
    if WINDOWS:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                                0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
                return winreg.QueryValueEx(k, "MachineGuid")[0]
        except OSError:
            return ""
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            return Path(p).read_text().strip()
        except OSError:
            pass
    return ""


# ---- Release all: confirm with the computer's password ----------------------------------------

RELEASE_CHECK = "/usr/libexec/anchor-release-check"  # Linux: installed with the polkit policy
RELEASE_POLICY = "/usr/share/polkit-1/actions/app.anchor.release.policy"


def system_password_check():
    """Asks for this computer's password with the system's own dialog. Anchor never keeps the
    password; it only learns whether it was right. Returns "ok", "cancelled", "denied" or "missing"."""
    return _windows_password_check() if WINDOWS else _polkit_password_check()


def _polkit_password_check():
    if not shutil.which("pkexec"):
        return "missing"
    command = RELEASE_CHECK if os.access(RELEASE_CHECK, os.X_OK) else "/bin/true"
    try:
        code = subprocess.run(["pkexec", "--disable-internal-agent", command],
                              capture_output=True, timeout=300).returncode
    except subprocess.TimeoutExpired:
        return "cancelled"
    return {0: "ok", 126: "cancelled"}.get(code, "denied")


def _windows_password_check():
    """The standard Windows security dialog, filled in with the signed-in user, then a logon check
    of what was typed (CredUIPromptForWindowsCredentials + LogonUser)."""
    import ctypes
    from ctypes import wintypes

    credui, advapi, kernel = ctypes.WinDLL("credui"), ctypes.WinDLL("advapi32"), ctypes.WinDLL("kernel32")

    class CREDUI_INFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("hwndParent", wintypes.HWND),
                    ("pszMessageText", wintypes.LPCWSTR), ("pszCaptionText", wintypes.LPCWSTR),
                    ("hbmBanner", wintypes.HBITMAP)]

    info = CREDUI_INFO(ctypes.sizeof(CREDUI_INFO), None,
                       "Enter your Windows password to release your anchored apps.", "Anchor", None)
    auth_package = wintypes.ULONG(0)
    out_buf, out_size = ctypes.c_void_p(), wintypes.ULONG(0)
    save = wintypes.BOOL(False)
    CREDUIWIN_ENUMERATE_CURRENT_USER = 0x200
    err = credui.CredUIPromptForWindowsCredentialsW(
        ctypes.byref(info), 0, ctypes.byref(auth_package), None, 0,
        ctypes.byref(out_buf), ctypes.byref(out_size), ctypes.byref(save), CREDUIWIN_ENUMERATE_CURRENT_USER)
    if err == 1223:  # ERROR_CANCELLED
        return "cancelled"
    if err != 0:
        return "missing"
    try:
        user, domain, password = (ctypes.create_unicode_buffer(514) for _ in range(3))
        sizes = [wintypes.DWORD(514) for _ in range(3)]
        CRED_PACK_PROTECTED_CREDENTIALS = 0x1  # decrypts the password so LogonUser can check it
        if not credui.CredUnPackAuthenticationBufferW(
                CRED_PACK_PROTECTED_CREDENTIALS, out_buf, out_size, user, ctypes.byref(sizes[0]), domain, ctypes.byref(sizes[1]),
                password, ctypes.byref(sizes[2])):
            return "denied"
        name, dom = user.value, domain.value or None
        if "\\" in name and not dom:
            dom, name = name.split("\\", 1)
        token = wintypes.HANDLE()
        LOGON32_LOGON_INTERACTIVE, LOGON32_PROVIDER_DEFAULT = 2, 0
        ok = advapi.LogonUserW(name, dom, password.value, LOGON32_LOGON_INTERACTIVE,
                               LOGON32_PROVIDER_DEFAULT, ctypes.byref(token))
        ctypes.memset(password, 0, ctypes.sizeof(password))
        if ok:
            kernel.CloseHandle(token)
            return "ok"
        return "denied"
    finally:
        ctypes.windll.ole32.CoTaskMemFree(out_buf)


def password_missing_text():
    if WINDOWS:
        return "Windows' password prompt couldn't be opened."
    return ("Anchor uses the system's password prompt (pkexec), which isn't installed. "
            "Install it with: sudo apt install pkexec")


# ---- Window chrome on Windows -------------------------------------------------------------------

APP_ID = "app.anchor.Desktop"


def set_app_id():
    """Groups Anchor's windows under its own icon on the Windows taskbar."""
    if WINDOWS:
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except (AttributeError, OSError):
            pass


def style_title_bar(hwnd, color=(0x0D, 0x0A, 0x14)):
    """Dark title bar in Anchor's background colour (Windows 10 20H1+, the colour on Windows 11)."""
    if not WINDOWS:
        return
    import ctypes
    from ctypes import wintypes
    dwm = ctypes.windll.dwmapi
    on = ctypes.c_int(1)
    DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_CAPTION_COLOR, DWMWA_BORDER_COLOR = 20, 35, 34
    try:
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(on), 4)
        r, g, b = color
        colorref = ctypes.c_uint(r | (g << 8) | (b << 16))
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), DWMWA_CAPTION_COLOR, ctypes.byref(colorref), 4)
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), DWMWA_BORDER_COLOR, ctypes.byref(colorref), 4)
    except (AttributeError, OSError):
        pass
