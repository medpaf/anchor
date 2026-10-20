import json
import urllib.error
import urllib.request
from pathlib import Path

REPO = "medpaf/anchor"
HERE = Path(__file__).resolve().parent

CURRENT, AVAILABLE, UNKNOWN = "current", "available", "unknown"

def current_build():

    try:
        return (HERE / "build-commit").read_text().strip() or None
    except OSError:
        return None

def latest_build(channel, timeout=10):

    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/git/ref/tags/{channel}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Anchor"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)["object"]["sha"]

def download_url(channel, filename):
    return f"https://github.com/{REPO}/releases/download/{channel}/{filename}"

def download(channel, filename, timeout=120):

    import tempfile
    folder = Path(tempfile.mkdtemp(prefix="anchor-update-"))
    path = folder / filename
    request = urllib.request.Request(download_url(channel, filename), headers={"User-Agent": "Anchor"})
    with urllib.request.urlopen(request, timeout=timeout) as response, open(path, "wb") as out:
        while chunk := response.read(64 * 1024):
            out.write(chunk)
    expected = {".deb": (b"!<arch>\n", "a Debian package"), ".exe": (b"MZ", "a Windows program")}
    for ending, (start, what) in expected.items():
        if filename.endswith(ending):
            with open(path, "rb") as f:
                if f.read(len(start)) != start:
                    raise OSError(f"The download isn't {what}")
    return path

def download_page(channel):
    return f"https://github.com/{REPO}/releases/tag/{channel}"

def check(channel):

    mine = current_build()
    if not mine:
        return UNKNOWN
    try:
        latest = latest_build(channel)
    except (KeyError, ValueError) as e:
        raise OSError(f"GitHub's answer didn't make sense: {e}") from e
    return CURRENT if latest == mine else AVAILABLE
