#!/usr/bin/env bash
# Builds the Linux downloads into free/linux/dist/:
#   anchor-linux.deb     Debian, Ubuntu, Linux Mint, Pop!_OS…   (sudo apt install ./anchor-linux.deb)
#   anchor-linux.tar.gz  any Linux: unpack, then run ./install.sh
#
# Needs dpkg-deb (on any Debian-based system). Writes only inside free/linux/build and free/linux/dist.
set -euo pipefail
LINUX="$(cd "$(dirname "$0")/.." && pwd)"
cd "$LINUX"

# Debian packages need a version number, and apt only installs a download over an older one when the
# number went up. Anchor doesn't show one anywhere, so it's simply when the package was built.
VERSION="1.0.$(date -u +%Y%m%d%H%M)"
STAGE="$LINUX/build/packages"
DIST="$LINUX/dist"
rm -rf -- "$STAGE" "$DIST"
mkdir -p "$STAGE" "$DIST"

APP_FILES=(desktop/anchor.py desktop/adbclient.py desktop/catalog.py desktop/keysheet.py desktop/permnames.py desktop/placeholder.py
           desktop/timetext.py desktop/updates.py desktop/anchor-agent.apk desktop/placeholder-manifest.bin)
# Builds made by GitHub record their commit, so Menu → Check for updates… can compare.
[ -f desktop/build-commit ] && APP_FILES+=(desktop/build-commit)
for f in "${APP_FILES[@]}" desktop/icons/*.svg polkit/anchor-release-check polkit/app.anchor.release.policy polkit/anchor-uninstall install.sh; do
  [ -f "$f" ] || { echo "Missing $f" >&2; exit 1; }
done

# ---- .deb: the same files install.sh puts in place, in the system's standard folders ----
DEB="$STAGE/deb"
install -d "$DEB/DEBIAN" "$DEB/usr/lib/anchor/icons" "$DEB/usr/bin" "$DEB/usr/share/applications" \
  "$DEB/usr/share/icons/hicolor/scalable/apps" "$DEB/usr/share/polkit-1/actions" "$DEB/usr/libexec" \
  "$DEB/usr/share/doc/anchor"
install -m 644 "${APP_FILES[@]}" "$DEB/usr/lib/anchor/"
install -m 644 desktop/icons/*.svg "$DEB/usr/lib/anchor/icons/"
install -m 644 desktop/icons/app.anchor.Desktop.svg "$DEB/usr/share/icons/hicolor/scalable/apps/"
# What App Center, GNOME Software and Discover show (name, developer, description, icon, links)
install -D -m 644 packaging/app.anchor.Desktop.metainfo.xml "$DEB/usr/share/metainfo/app.anchor.Desktop.metainfo.xml"
for size in 48 64 128 256 512; do  # store apps prefer PNG icons
  install -D -m 644 "packaging/icons/$size.png" "$DEB/usr/share/icons/hicolor/${size}x${size}/apps/app.anchor.Desktop.png"
done
install -m 644 polkit/app.anchor.release.policy "$DEB/usr/share/polkit-1/actions/"
install -m 755 polkit/anchor-release-check "$DEB/usr/libexec/"
# "Uninstall Anchor from this computer…" runs this through pkexec: it removes the package itself.
printf '%s\n' '#!/bin/sh' \
  '# Removes the Anchor package. Run by Anchor'"'"'s "Uninstall Anchor from this computer…" through pkexec.' \
  'exec dpkg --remove anchor' > "$DEB/usr/libexec/anchor-uninstall"
chmod 755 "$DEB/usr/libexec/anchor-uninstall"
# Menu → Check for updates… → Update runs this through pkexec: it installs the downloaded .deb.
install -m 755 packaging/anchor-update "$DEB/usr/libexec/anchor-update"

cat > "$DEB/usr/bin/anchor" <<'EOF'
#!/bin/sh
exec python3 /usr/lib/anchor/anchor.py "$@"
EOF
chmod 755 "$DEB/usr/bin/anchor"

cat > "$DEB/usr/share/applications/app.anchor.Desktop.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Anchor
Comment=Block distracting apps on your Android phone
Exec=anchor
Icon=app.anchor.Desktop
Terminal=false
Categories=Utility;
Keywords=android;phone;block;focus;screen time;anchor;
StartupWMClass=app.anchor.Desktop
EOF

cat > "$DEB/usr/share/doc/anchor/copyright" <<'EOF'
Anchor, by Paulo Medeiros <pafmed@protonmail.com>
https://github.com/medpaf/anchor

Copyright (C) 2026 Paulo Medeiros
License: PolyForm Strict 1.0.0 (source-available, not open source)

EOF
cat "$LINUX/../../LICENSE" >> "$DEB/usr/share/doc/anchor/copyright"

chmod 644 "$DEB/usr/share/applications/app.anchor.Desktop.desktop" "$DEB/usr/share/doc/anchor/copyright"

SIZE=$(du -sk "$DEB/usr" | cut -f1)
cat > "$DEB/DEBIAN/control" <<EOF
Package: anchor
Version: $VERSION
Architecture: all
Maintainer: Paulo Medeiros <pafmed@protonmail.com>
Installed-Size: $SIZE
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1 (>= 1.5), adb, openssl, pkexec | policykit-1
Section: utils
Priority: optional
Homepage: https://github.com/medpaf/anchor
Description: Block distracting apps on your Android phone
 Anchor hides the apps you pick on your Android phone, and only this computer
 can bring them back, over a USB cable. Free version: one phone per computer.
EOF

dpkg-deb --build --root-owner-group "$DEB" "$DIST/anchor-linux.deb" >/dev/null

# ---- .tar.gz: the app plus install.sh, for any Linux ----
TAR="$STAGE/anchor-linux"
mkdir -p "$TAR/desktop/icons" "$TAR/polkit"
cp "${APP_FILES[@]}" "$TAR/desktop/"
cp desktop/icons/*.svg "$TAR/desktop/icons/"
cp polkit/* "$TAR/polkit/"
cp install.sh "$TAR/"
cp "$LINUX/../../LICENSE" "$TAR/LICENSE"
tar -C "$STAGE" --owner=0 --group=0 --mode=go-w -czf "$DIST/anchor-linux.tar.gz" anchor-linux

echo "Built:"
ls -l "$DIST"
