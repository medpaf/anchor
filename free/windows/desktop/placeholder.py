"""Builds "placeholder" APKs: tiny empty apps that take a never-allowed app's package name.

With a placeholder installed under, say, com.reddit.frontpage, Android refuses to install the real
Reddit (an app with that name already exists, signed with a different key), so the Play Store can't
install it. The phone keeps placeholders hidden and removes them when the app is released.

An APK here is just the compiled manifest (placeholder-manifest.bin, made from
android/placeholder/AndroidManifest.xml by android/build.sh) with the package name swapped in, plus a
v1 (JAR) signature made with Python's cryptography library. No Android SDK or openssl is needed,
so it works the same on Windows and Linux.
"""

import base64
import hashlib
import io
import datetime
import os
import struct
import tempfile
import zipfile
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

import platform_support as plat

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


# ---- Signing (v1 / JAR signature) ----------------------------------------------------------

def key_dir():
    return plat.data_dir() / "placeholder-key"


def ensure_key():
    """A self-signed key, made once. Every placeholder is signed with it."""
    d = key_dir()
    key_path, cert_path = d / "key.pem", d / "cert.pem"
    if not (key_path.exists() and cert_path.exists()):
        d.mkdir(parents=True, exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Anchor placeholder")])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(now)
                .not_valid_after(now + datetime.timedelta(days=36500)).sign(key, hashes.SHA256()))
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
        if not plat.WINDOWS:
            os.chmod(key_path, 0o600)
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key_path, cert_path


def _sign(data):
    """A detached PKCS#7 signature of `data` in DER, as `openssl cms -sign -binary -noattr` makes."""
    key_path, cert_path = ensure_key()
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    options = [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary, pkcs7.PKCS7Options.NoAttributes]
    return (pkcs7.PKCS7SignatureBuilder().set_data(data).add_signer(cert, key, hashes.SHA256())
            .sign(serialization.Encoding.DER, options))


def _b64sha256(data):
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


def build_apk(package):
    """Returns the bytes of a signed placeholder APK for `package`."""
    manifest_xml = manifest_for(package)
    entry = f"Name: AndroidManifest.xml\r\nSHA-256-Digest: {_b64sha256(manifest_xml)}\r\n\r\n".encode()
    mf = b"Manifest-Version: 1.0\r\nCreated-By: Anchor\r\n\r\n" + entry
    sf = (f"Signature-Version: 1.0\r\nSHA-256-Digest-Manifest: {_b64sha256(mf)}\r\n"
          f"Created-By: Anchor\r\n\r\nName: AndroidManifest.xml\r\nSHA-256-Digest: {_b64sha256(entry)}\r\n\r\n").encode()
    signature = _sign(sf)
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
