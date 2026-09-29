#!/bin/bash
# Installe Visiolux : visuels rétro-terminal sur la sortie composite
# + page web de contrôle (http://<nom-du-pi>.local).
# Cible : Raspberry Pi OS Lite (Bookworm ou plus récent).
# Usage : sudo ./install.sh [PAL|SECAM|NTSC]
set -e

NORM="${1:-PAL}"
DIR="$(cd "$(dirname "$0")" && pwd)"
CFG=/boot/firmware/config.txt
CMD=/boot/firmware/cmdline.txt
FICHIERS="app.py moteur.py scenes.py page.html"

[ "$EUID" -eq 0 ] || { echo "Lancer avec sudo"; exit 1; }
for f in $FICHIERS; do
  [ -f "$DIR/$f" ] || { echo "Fichier manquant : $f"; exit 1; }
done

echo "== Paquets"
apt-get update
apt-get install -y python3-flask python3-pil python3-numpy fonts-dejavu-core

echo "== Programme"
install -d /opt/visiolux /var/lib/visiolux
for f in $FICHIERS; do install -m 644 "$DIR/$f" /opt/visiolux/; done
sed -i 's/\r$//' /opt/visiolux/*          # fins de ligne Windows éventuelles

echo "== Sortie composite"
cp -n "$CFG" "$CFG.bak" || true
if grep -q '^dtoverlay=vc4-kms-v3d' "$CFG"; then
  grep -q '^dtoverlay=vc4-kms-v3d.*composite' "$CFG" || \
    sed -i 's/^dtoverlay=vc4-kms-v3d\(.*\)$/dtoverlay=vc4-kms-v3d\1,composite/' "$CFG"
else
  echo 'dtoverlay=vc4-kms-v3d,composite' >> "$CFG"
fi
grep -q '^disable_splash=1' "$CFG" || echo 'disable_splash=1' >> "$CFG"

cp -n "$CMD" "$CMD.bak" || true
sed -i -E 's/ ?(vc4\.tv_norm|video=Composite-1|consoleblank|vt\.global_cursor_default|logo\.nologo|loglevel)=?[^ ]*//g; s/ quiet( |$)/\1/g' "$CMD"
if [ "$NORM" = "NTSC" ]; then MODE="720x480@60ie"; else MODE="720x576@50ie"; fi
sed -i "1 s/\$/ vc4.tv_norm=$NORM video=Composite-1:$MODE consoleblank=0 vt.global_cursor_default=0 logo.nologo quiet loglevel=3/" "$CMD"

echo "== Service"
systemctl disable --now aperture-logo.service 2>/dev/null || true
systemctl disable getty@tty1.service 2>/dev/null || true
cat > /etc/systemd/system/visiolux.service <<'EOF'
[Unit]
Description=Visiolux - visuels retro sur ecran composite + page web
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/visiolux
ExecStart=/usr/bin/python3 /opt/visiolux/app.py
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable visiolux.service

echo
echo "OK. Redémarre avec : sudo reboot"
echo "Puis ouvre sur ton téléphone : http://$(hostname).local"
