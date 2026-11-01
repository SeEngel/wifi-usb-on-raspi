# Engineering notes — running log (inverse: newest on top)

## 2026-11-01 — v1 build & banach environment facts
- banach = Raspi 4, Debian 12 bookworm (arm64), kernel **6.12.20+rpt-rpi-v8**.
- `apt-cache search usbip` → package **`usbip`** exists (usbipd + client in one pkg).
- Kernel modules shipped in stock kernel image at
  `/lib/modules/6.12.20+rpt-rpi-v8/kernel/drivers/usb/usbip/`: `usbip-core.ko.xz`,
  `usbip-host.ko.xz`, `usbip-vudc.ko.xz`, `vhci-hcd.ko.xz` — no DKMS needed. ✔
- sudo **passwordless** for user `banach` in our SSH context.
- Client-side reality (recorded for honesty): the J.A.R.V.I.S. agent OS is a proot
  container on an Android kernel — **cannot** load `vhci_hcd` and cannot see
  `/dev/bus/usb`; loopback on banach itself (`vhci_hcd` IS available there) is the
  authoritative first E2E client test. Recorded in Plan.md Q1.
