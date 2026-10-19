#!/usr/bin/env bash
# Installs Anchor for the current user: app files, a launcher entry and an `anchor` command (no sudo).
# Then, with sudo, the polkit policy that words the Release all password prompt (optional).

sudo apt install adb openssl python3-gi python3-cairo gir1.2-gtk-4.0 gir1.2-adw-1

set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f desktop/anchor-agent.apk ]; then
  echo "desktop/anchor-agent.apk is missing. Build it first: ./android/build.sh" >&2
  exit 1
fi
if ! python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1')" 2>/dev/null; then
  echo "Missing GTK 4 / libadwaita for Python. Install them with:" >&2
  echo "  sudo apt install python3-gi python3-cairo gir1.2-gtk-4.0 gir1.2-adw-1" >&2
  exit 1
fi
if ! command -v adb >/dev/null && [ ! -x "$HOME/Android/Sdk/platform-tools/adb" ]; then
  echo "Note: adb not found. Install it with: sudo apt install adb" >&2
fi

DEST="$HOME/.local/share/anchor-app"
mkdir -p "$DEST" "$HOME/.local/bin" "$HOME/.local/share/applications" \
  "$HOME/.local/share/icons/hicolor/scalable/apps"
cp -r desktop/. "$DEST/"
cp desktop/icons/app.anchor.Desktop.svg "$HOME/.local/share/icons/hicolor/scalable/apps/"

cat > "$HOME/.local/bin/anchor" <<EOF
#!/bin/sh
exec python3 "$DEST/anchor.py" "\$@"
EOF
chmod +x "$HOME/.local/bin/anchor"

cat > "$HOME/.local/share/applications/app.anchor.Desktop.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Anchor
Comment=Block distracting apps on your Android phone
Exec=python3 $DEST/anchor.py
Icon=app.anchor.Desktop
Terminal=false
Categories=Utility;
Keywords=android;phone;block;focus;screen time;anchor;
StartupWMClass=app.anchor.Desktop
EOF
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

# Optional, needs sudo: gives the Release all password prompt its own wording. Without it the
# prompt still works but says "Authentication is needed to run `/bin/true` as the super user".
POLICY=/usr/share/polkit-1/actions/app.anchor.release.policy
HELPER=/usr/libexec/anchor-release-check
UNINSTALL=/usr/libexec/anchor-uninstall
if ! cmp -s polkit/app.anchor.release.policy "$POLICY" || ! cmp -s polkit/anchor-release-check "$HELPER" ||
   ! cmp -s polkit/anchor-uninstall "$UNINSTALL"; then
  echo "Installing the password prompt text (needs sudo, three small system files)…"
  if sudo install -D -m 755 -o root -g root polkit/anchor-release-check "$HELPER" &&
     sudo install -D -m 755 -o root -g root polkit/anchor-uninstall "$UNINSTALL" &&
     sudo install -D -m 644 -o root -g root polkit/app.anchor.release.policy "$POLICY"; then
    echo "Password prompt text installed."
  else
    echo "Skipped. The Release all prompt will use the system's generic wording." >&2
  fi
fi

echo "Anchor installed. Open it from your app grid, or run: anchor"
