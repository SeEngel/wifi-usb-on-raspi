#!/usr/bin/env bash
# uninstall.sh - wifi-usb-on-raspi
# Removes everything install.sh brought onto this machine.
# Keeps a backup of the config; USB devices are returned to LOCAL use first.
#
# Usage (as root):
#   sudo ./uninstall.sh        # remove system integration, keep packages + config backup
#   sudo ./uninstall.sh --purge # additionally remove the 'usbip' apt package and the config
set -euo pipefail

PURGE=0
[[ "${1:-}" == "--purge" ]] && PURGE=1

say() { echo "[uninstall] $*"; }

if [[ $EUID -ne 0 ]]; then
  echo "error: run me with sudo: sudo ./uninstall.sh"
  exit 1
fi

# 1. stop services, return devices to the local machine first
say "stopping services (devices return to local use) ..."
systemctl disable --now wirehubd.service usbipd.service >/dev/null 2>&1 || true
for b in /sys/bus/usb/drivers/usbip_host/* 2>/dev/null; do
  [[ -e "$b" ]] || continue
  busid="$(basename "$b" | cut -d: -f1)"
  say "unbinding ${busid} ..."
  usbip unbind -b "$busid" >/dev/null 2>&1 || true
done

rm -f /etc/systemd/system/wirehubd.service /etc/systemd/system/usbipd.service
systemctl daemon-reload

# 2. files
rm -f /usr/local/bin/wirehub
rm -rf /usr/local/lib/wirehub
rm -f /etc/modules-load.d/wirehub.conf
say "system files removed"

# 3. config -> backup (or real removal with --purge)
if [[ -d /etc/wirehub ]] && [[ $PURGE -eq 0 ]]; then
  dest="/var/backups/wirehub/$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$dest"
  cp -a /etc/wirehub/config.json "$dest/" 2>/dev/null || true
  say "config backed up to ${dest}"
else
  rm -rf /etc/wirehub
  say "config removed"
fi

# 4. optional package removal
if [[ $PURGE -eq 1 ]]; then
  apt-get remove -y -qq usbip >/dev/null 2>&1 || true
  say "'usbip' apt package removed"
fi

# 5. verify
if ss -ltn 2>/dev/null | grep -q ':3240 '; then
  say "WARNING: something still listens on 3240 (maybe another process)"
else
  say "port 3240 closed"
fi
say "REMOVED. (Loaded kernel modules stay in memory until next reboot - harmless.)"
