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

## 2026-11-01 — ESP32-S3-Touch-LCD-1.69 E2E PASS + device matrix
- Board: Waveshare ESP32-S3-Touch-LCD-1.69, **native ESP32-S3 USB** (kein CH343!) — subagent-verified.
  Enumeration: `303a:1001` (USB-Serial/JTAG ROM) oder `303a:4001` (TinyUSB CDC der App-Firmware).
  Buttons: PWR nur relevant bei Batteriebetrieb; BOOT+RST = Download-Modus (303a:1001 garantiert).
- E2E: export (bind) → loopback attach → `cdc_acm: ttyACM0` am virtuellen Bus 003 ✔
- Allowlist-Zuwachs: rule `esp32-touch-lcd-1.69` (vid 303a, pid 1001), plus `trust-keyboard` (145f:02c9).
- **Device matrix (both directions live over USB/IP):** mouse ✔ / keyboard ✔ / ESP32-S3 serial ✔.
- Kabel-Lektion: Tausende USB-C-Kabel sind lade-only (D+/D− fehlen) → LCD glüht, aber keine Enumeration.
  Diagnostic flow: lsusb → cdc/dmesg → RST → der definitive Download-Modus (BOOT halten + RST).
