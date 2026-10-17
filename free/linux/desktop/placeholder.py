"""Builds "placeholder" APKs: tiny empty apps that take a never-allowed app's package name.

With a placeholder installed under, say, com.reddit.frontpage, Android refuses to install the real
Reddit (an app with that name already exists, signed with a different key), so the Play Store can't
install it. The phone keeps placeholders hidden and removes them when the app is released.

An APK here is just the compiled manifest (placeholder-manifest.bin, made from
android/placeholder/AndroidManifest.xml by android/build.sh) with the package name swapped in, plus a
v1 (JAR) signature made with openssl. No Android SDK is needed.
"""

import base64
import hashlib
import io
import os
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "placeholder-manifest.bin"
TEMPLATE_PACKAGE = "app.anchor.placeholder.template"

RES_STRING_POOL_TYPE = 0x0001
UTF8_FLAG = 1 << 8
SORTED_FLAG = 1 << 0


class PlaceholderError(Exception):
    pass


# ---- Binary XML (AXML) string pool -------------------------------------------------------

def _read_len8(data, pos):
    n = data[pos]
    if n & 0x80:
        return ((n & 0x7F) << 8) | data[pos + 1], pos + 2
    return n, pos + 1


def _read_len16(data, pos):
    n = struct.unpack_from("<H", data, pos)[0]
    if n & 0x8000:
        return ((n & 0x7FFF) << 16) | struct.unpack_from("<H", data, pos + 2)[0], pos + 4
    return n, pos + 2


def _enc_len8(n):
    return bytes([n]) if n < 0x80 else bytes([0x80 | (n >> 8), n & 0xFF])


def _parse_pool(chunk):
    _type, header_size, _size, count, styles, flags, strings_start, _styles_start = struct.unpack_from(
        "<HHIIIIII", chunk, 0)
    if styles:
        raise PlaceholderError("unexpected styled strings in the manifest template")
    offsets = struct.unpack_from(f"<{count}I", chunk, header_size)
    out = []
    for off in offsets:
        pos = strings_start + off
        if flags & UTF8_FLAG:
            _chars, pos = _read_len8(chunk, pos)
            nbytes, pos = _read_len8(chunk, pos)
            out.append(chunk[pos:pos + nbytes].decode("utf-8"))
        else:
            nchars, pos = _read_len16(chunk, pos)
            out.append(chunk[pos:pos + 2 * nchars].decode("utf-16-le"))
    return out, flags, header_size


def _build_pool(strings, flags):
    flags &= ~SORTED_FLAG  # we change a string, so don't promise any order
    data, offsets = bytearray(), []
    for s in strings:
        offsets.append(len(data))
        if flags & UTF8_FLAG:
            raw = s.encode("utf-8")
            data += _enc_len8(len(s)) + _enc_len8(len(raw)) + raw + b"\x00"
        else:
            raw = s.encode("utf-16-le")
            n = len(raw) // 2
            data += (struct.pack("<H", n) if n < 0x8000 else struct.pack("<HH", 0x8000 | (n >> 16), n & 0xFFFF))
            data += raw + b"\x00\x00"
    while len(data) % 4:
        data += b"\x00"
    header_size = 28
    strings_start = header_size + 4 * len(strings)
    size = strings_start + len(data)
    header = struct.pack("<HHIIIIII", RES_STRING_POOL_TYPE, header_size, size, len(strings), 0, flags,
                         strings_start, 0)
    return header + struct.pack(f"<{len(strings)}I", *offsets) + bytes(data)


def manifest_for(package):
    """The compiled template manifest with its package name replaced."""
    axml = TEMPLATE.read_bytes()
    xml_type, xml_header, _xml_size = struct.unpack_from("<HHI", axml, 0)
    if xml_type != 0x0003:
        raise PlaceholderError("placeholder-manifest.bin isn't a compiled Android manifest")
    pool_size = struct.unpack_from("<I", axml, xml_header + 4)[0]
    pool = axml[xml_header:xml_header + pool_size]
    strings, flags, _ = _parse_pool(pool)
    if TEMPLATE_PACKAGE not in strings:
        raise PlaceholderError("the template's package name is missing; rebuild with android/build.sh")
    strings = [package if s == TEMPLATE_PACKAGE else s for s in strings]
    new_pool = _build_pool(strings, flags)
    rest = axml[xml_header + pool_size:]
    body = new_pool + rest
    return struct.pack("<HHI", 0x0003, xml_header, xml_header + len(body)) + axml[8:xml_header] + body


# ---- Signing (v1 / JAR signature, via openssl) ---------------------------------------------

def key_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "anchor" / "placeholder-key"


def ensure_key():
    d = key_dir()
    key, cert = d / "key.pem", d / "cert.pem"
    if not (key.exists() and cert.exists()):
        d.mkdir(parents=True, exist_ok=True)
        _openssl(["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert),
                  "-days", "36500", "-subj", "/CN=Anchor placeholder"])
        os.chmod(key, 0o600)
    return key, cert


def _openssl(args, data=None):
    try:
        p = subprocess.run(["openssl", *args], input=data, capture_output=True, timeout=60)
    except FileNotFoundError:
        raise PlaceholderError("openssl is missing. Install it with: sudo apt install openssl")
    if p.returncode != 0:
        raise PlaceholderError("openssl failed: " + p.stderr.decode(errors="replace").strip())
    return p.stdout


def _b64sha256(data):
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


def build_apk(package):
    """Returns the bytes of a signed placeholder APK for `package`."""
    manifest_xml = manifest_for(package)
    entry = f"Name: AndroidManifest.xml\r\nSHA-256-Digest: {_b64sha256(manifest_xml)}\r\n\r\n".encode()
    mf = b"Manifest-Version: 1.0\r\nCreated-By: Anchor\r\n\r\n" + entry
    sf = (f"Signature-Version: 1.0\r\nSHA-256-Digest-Manifest: {_b64sha256(mf)}\r\n"
          f"Created-By: Anchor\r\n\r\nName: AndroidManifest.xml\r\nSHA-256-Digest: {_b64sha256(entry)}\r\n\r\n").encode()
    key, cert = ensure_key()
    signature = _openssl(["cms", "-sign", "-binary", "-noattr", "-outform", "DER", "-md", "sha256",
                          "-signer", str(cert), "-inkey", str(key), "-nosmimecap"], data=sf)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("AndroidManifest.xml", manifest_xml)
        z.writestr("META-INF/MANIFEST.MF", mf)
        z.writestr("META-INF/ANCHOR.SF", sf)
        z.writestr("META-INF/ANCHOR.RSA", signature)
    return buf.getvalue()


def write_apk(package, directory=None):
    """Builds a placeholder APK into a temporary file and returns its path."""
    fd, path = tempfile.mkstemp(prefix="anchor-placeholder-", suffix=".apk", dir=directory)
    with os.fdopen(fd, "wb") as f:
        f.write(build_apk(package))
    return Path(path)
