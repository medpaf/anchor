import socket
from datetime import datetime

FILENAME = "Anchor backup key.pdf"

def page(key, phone="", now=None):

    when = f"{now or datetime.now():%d %B %Y}".lstrip("0")
    computer = socket.gethostname() or "this computer"
    saved = f"Saved on {when} from {computer}" + (f", paired with {phone}" if phone else "") + "."
    return [
        ("title", "Anchor backup key"),
        ("key", key),
        ("small", saved),
        ("text", "This key is what lets a computer release the apps Anchor hides on your phone. Keep this "
                 "page somewhere safe that you can't reach on impulse, away from the phone. It still works "
                 "after Anchor is uninstalled from the computer."),
        ("heading", "To use it"),
        ("text", "Install Anchor on a computer (github.com/medpaf/anchor), connect your phone with a USB "
                 "cable, then choose “Use a backup key…” in the Anchor menu and type the key above."),
        ("heading", "If you lose it"),
        ("text", "Without this key or the computer it came from, the only way to get your apps back is a "
                 "factory reset of the phone, which erases everything on it."),
    ]
