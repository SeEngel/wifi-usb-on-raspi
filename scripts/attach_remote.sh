#!/usr/bin/env bash
# attach_remote.sh - helper for any Linux client (one-time already done: apt install usbip, modprobe vhci_hcd)
set -euo pipefail
HOST="${1:?usage: sudo ./attach_remote.sh <host|IP|host.local> [busid]}"
BUSID="${2:-}"

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "needs sudo (usbip attach needs root)"; exit 1; }
modprobe vhci_hcd 2>/dev/null || true

usbip list -r "$HOST"
if [[ -z "$BUSID" ]]; then
  echo
  echo "pick a busid above and re-run: sudo $0 $HOST <busid>"
  exit 0
fi

usbip attach -r "$HOST" -b "$BUSID" && echo "attached: $BUSID from $HOST is now a local USB device on this machine"
