"""Checks GitHub for a newer build of Anchor. Only runs when you choose Menu → Check for updates…

Each download that GitHub builds records the commit it was built from in build-commit, next to this
file. The newest download for each system is published on a release whose tag ("linux" or
"windows") points at the commit it was built from. If the two commits differ, there's a newer build.

The only thing sent is the request for that tag: nothing about you or your phone."""

import json
import urllib.error
import urllib.request
from pathlib import Path

REPO = "medpaf/anchor"
HERE = Path(__file__).resolve().parent

CURRENT, AVAILABLE, UNKNOWN = "current", "available", "unknown"


def current_build():
    """The commit this copy was built from, or None when it wasn't built by GitHub (e.g. from source)."""
    try:
        return (HERE / "build-commit").read_text().strip() or None
    except OSError:
        return None


def latest_build(channel, timeout=10):
    """The commit the newest download for `channel` ("linux" or "windows") was built from."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/git/ref/tags/{channel}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Anchor"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https URL
        return json.load(response)["object"]["sha"]


def download_url(channel, filename):
    return f"https://github.com/{REPO}/releases/download/{channel}/{filename}"


def download(channel, filename, timeout=120):
    """Downloads the newest `filename` (e.g. "anchor-linux.deb") into a new private temporary folder
    and returns its path. Raises OSError when it can't, or when the file isn't a Debian package."""
    import tempfile
    folder = Path(tempfile.mkdtemp(prefix="anchor-update-"))
    path = folder / filename
    request = urllib.request.Request(download_url(channel, filename), headers={"User-Agent": "Anchor"})
    with urllib.request.urlopen(request, timeout=timeout) as response, open(path, "wb") as out:  # noqa: S310
        while chunk := response.read(64 * 1024):
            out.write(chunk)
    if filename.endswith(".deb"):
        with open(path, "rb") as f:
            if f.read(8) != b"!<arch>\n":  # every .deb starts like this
                raise OSError("The download isn't a Debian package")
    return path


def download_page(channel):
    return f"https://github.com/{REPO}/releases/tag/{channel}"


def check(channel):
    """CURRENT, AVAILABLE or UNKNOWN (this copy wasn't built by GitHub, so there's nothing to compare).
    Raises OSError (urllib's errors included) when GitHub can't be reached."""
    mine = current_build()
    if not mine:
        return UNKNOWN
    try:
        latest = latest_build(channel)
    except (KeyError, ValueError) as e:
        raise OSError(f"GitHub's answer didn't make sense: {e}") from e
    return CURRENT if latest == mine else AVAILABLE
