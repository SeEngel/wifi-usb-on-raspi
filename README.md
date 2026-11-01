# wifi-usb-on-raspi

Use a Raspberry Pi as a **Wi-Fi USB hub**: USB devices plugged into the Pi become
usable on *other* machines over the network **as if they were plugged in locally**
(protocol: [USB/IP](https://www.kernel.org/doc/html/latest/driver_api/usb/usbip.html)).

Built and proven on Raspberry Pi 4 / Debian 12 bookworm (`banach`).

## TL;DR (server = the Pi)

```bash
# install once (creates systemd services, power-on ready, no login needed):
git clone https://github.com/SeEngel/wifi-usb-on-raspi.git
cd wifi-usb-on-raspi
sudo ./install.sh
# -> put your devices into /etc/wirehub/config.json (allowlist) — see example
```

Uninstall: `sudo ./uninstall.sh` (add `--purge` to also remove the package).

## TL;DR (client = the machine that wants the USB device)

The Pi is reachable as **`banach.local`** (mDNS; also survives Wi-Fi changes because
the name is broadcast by the Pi itself; port TCP/3240):

```bash
sudo usbip list -r banach.local            # see what is shared
sudo usbip attach -r banach.local -b 1-1.4 # attach a device -> appears in lsusb
sudo usbip detach -r banach.local -b 1-1.4 # release it
```

Linux client one-time setup: `sudo apt install usbip && sudo modprobe vhci_hcd`.
Windows (10/11): via WSL2 or usbip-win — see `docs/clients-windows.md`.
Details/spec of every client step: `docs/clients-linux.md`.

## How it works

```
USB device -> Pi sysfs -> usbip_host kernel module -> usbipd (TCP 3240)
                                                    -> wirehubd (Python, auto-exports allowlist devices)
client: usbip attach -> vhci_hcd -> real USB device on the client
```

Components in this repo:

| Path | Role |
|---|---|
| `src/wirehubd.py` | daemon: hotplug watcher + auto-export + status JSON API |
| `src/wirehublib.py` | shared logic (sysfs, usbip calls) |
| `src/wirehub` | CLI: `status / list / export / unexport / config-check / tail` |
| `systemd/*.service` | boot integration (headless power-on ready, restart-safe) |
| `install.sh` / `uninstall.sh` | one-shot setup / clean removal |
| `Plan.md` | the master plan, phases with checklists |
| `config/wirehub.example.json` | allowlist config template |
| `docs/` | client guides + engineering notes |

## Security (honest)

USB/IP has **no authentication and no encryption**. Only use on a trusted LAN.
Do not port-forward it to the internet.

## Plan / status

See **`Plan.md`** for the full implementation plan with phases and checklists.
