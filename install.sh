#!/usr/bin/env bash
# install.sh - wifi-usb-on-raspi
# Installs the USB/IP server stack (usbipd + wirehubd) on this machine and
# enables it at boot (systemd). Power-on ready, no login needed.
#
# Usage (as root):
#   sudo ./install.sh              # normal install
#   sudo ./install.sh --no-apt     # skip apt-get (packages already there / offline)
#   sudo ./install.sh --config F   # use a specific wirehub config file
#   sudo ./install.sh --force      # overwrite an existing /etc/wirehub/config.json
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
LIBDIR="/usr/local/lib/wirehub"
CONFDIR="/etc/wirehub"
CONF="${CONFDIR}/config.json"
NO_APT=0
FORCE=0
CUSTOM_CFG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-apt) NO_APT=1; shift ;;
    --config) CUSTOM_CFG="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown option: $1"; exit 2 ;;
  esac
done

say() { echo "[install] $*"; }

if [[ $EUID -ne 0 ]]; then
  echo "error: run me with sudo: sudo ./install.sh"
  exit 1
fi

# --- 1. packages -------------------------------------------------------------
if [[ $NO_APT -eq 0 ]]; then
  say "installing apt packages (usbip, python3) ..."
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq usbip python3 >/dev/null
fi

USBIPD_BIN="$(command -v usbipd || true)"
[[ -n "$USBIPD_BIN" ]] || { echo "error: 'usbipd' binary not found (did 'apt-get install usbip' succeed?)"; exit 1; }
say "usbipd found at: ${USBIPD_BIN}"

# Debian installs the 'usbip' client into /usr/sbin which is not on the default
# user PATH -> symlink it into /usr/local/bin so 'usbip' just works everywhere.
USBIP_BIN="$(command -v usbip || true)"
if [[ -n "$USBIP_BIN" && "$(dirname "$USBIP_BIN")" != "/usr/local/bin" ]]; then
  ln -sf "$USBIP_BIN" /usr/local/bin/usbip
  say "symlinked ${USBIP_BIN} -> /usr/local/bin/usbip"
fi

# --- 2. kernel modules (load now + persist at boot) ---------------------------
modprobe usbip_core 2>/dev/null || echo "note: usbip_core module did not load (reboot may be needed)"
modprobe usbip_host 2>/dev/null || echo "note: usbip_host module did not load (reboot may be needed)"
printf '%s\n' usbip_core usbip_host > /etc/modules-load.d/wirehub.conf
say "kernel modules loaded + persisted (/etc/modules-load.d/wirehub.conf)"

# --- 3. files -----------------------------------------------------------------
say "installing daemon + CLI ..."
install -d "${LIBDIR}"
install -m 0644 "${HERE}/src/wirehublib.py" "${HERE}/src/wirehubd.py" "${LIBDIR}/"
install -m 0755 "${HERE}/src/wirehub" /usr/local/bin/wirehub

say "installing config ..."
install -d "${CONFDIR}"
if [[ ! -f "${CONF}" || $FORCE -eq 1 ]]; then
  if [[ -n "$CUSTOM_CFG" ]]; then
    install -m 0644 "${CUSTOM_CFG}" "${CONF}"
  else
    install -m 0644 "${HERE}/config/wirehub.example.json" "${CONF}"
  fi
  say "config written: ${CONF}  (EDIT THE ALLOWLIST TO YOUR DEVICES!)"
else
  say "config kept: ${CONF} (exists; use --force to overwrite)"
fi
python3 /usr/local/bin/wirehub --config "${CONF}" config-check >/dev/null 2>&1 \
  && say "config check: ok" \
  || echo "config check FAILED - fix ${CONF} before your devices will be shared"

# --- 4. systemd units ----------------------------------------------------------
say "installing systemd units ..."
sed "s|@USBIPD@|${USBIPD_BIN}|g" "${HERE}/systemd/usbipd.service"   > /etc/systemd/system/usbipd.service
install -m 0644 "${HERE}/systemd/wirehubd.service" /etc/systemd/system/wirehubd.service
systemctl daemon-reload
systemctl enable --now usbipd.service >/dev/null 2>&1 || true
systemctl enable --now wirehubd.service >/dev/null 2>&1 || true
sleep 2

# --- 5. firewall (USB/IP restricted to private networks) + mDNS ad -------------
say "firewall (nftables: USB/IP for private networks only) ..."
if [[ -e /etc/nftables.conf && ! -e /etc/nftables.conf.pre-wirehub ]]; then
  cp -a /etc/nftables.conf /etc/nftables.conf.pre-wirehub
  say "  existing nftables.conf backed up to /etc/nftables.conf.pre-wirehub"
fi
if install -m 0644 "${HERE}/fw/nftables.conf" /etc/nftables.conf; then
  /usr/sbin/nft -f /etc/nftables.conf && systemctl enable nftables >/dev/null 2>&1 \
    && say "  firewall applied + enabled (backup: /etc/nftables.conf.pre-wirehub)" \
    || echo "  warning: nftables apply failed - USB/IP stays open (check manually)"
fi
say "mDNS advertisement (_usbip._tcp) ..."
install -d /etc/avahi/services
install -m 0644 "${HERE}/avahi/usbip.service" /etc/avahi/services/usbip.service
systemctl restart avahi-daemon 2>/dev/null || true

# --- 6. verification -----------------------------------------------------------
fail=0
systemctl is-active --quiet usbipd.service  && say "usbipd.service: ACTIVE"   || { say "usbipd.service: NOT active"; fail=1; }
systemctl is-active --quiet wirehubd.service && say "wirehubd.service: ACTIVE" || { say "wirehubd.service: NOT active"; fail=1; }
if ss -ltn 2>/dev/null | grep -q ':3240 '; then
  say "port TCP/3240: LISTENING (USB/IP server reachable from clients)"
else
  say "port TCP/3240: NOT listening - check 'journalctl -u usbipd -n 20'"
  fail=1
fi
curl -s "http://127.0.0.1:22824/status" | grep -q '"host"' 2>/dev/null \
  && say "status API: responding (127.0.0.1:22824/status)" \
  || say "status API: not responding (config 'statusApi' disabled?)"

HOSTN="$(hostname)"
if [[ $fail -eq 0 ]]; then
  say "----------------------------------------------"
  say "READY. This machine now shares USB over USB/IP."
  say "reach it   : ${HOSTN}.local  (mDNS; also survives Wi-Fi changes)"
  say "  fallback : $(hostname -I 2>/dev/null | awk '{print $1}')  (IP, may change)"
  say "client cmds: usbip list -r ${HOSTN}.local"
  say "             sudo usbip attach -r ${HOSTN}.local -b <busid>"
  say "  helpers  : wirehub status / list / export / unexport"
  say "----------------------------------------------"
  exit 0
else
  say "installed but NOT fully healthy - see messages above"
  exit 1
fi
