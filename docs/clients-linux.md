# Linux clients (Debian/Ubuntu/…, incl. a Pi used as client)

## One-time setup on the client machine

```bash
sudo apt install usbip
sudo modprobe vhci_hcd                  # the client-side virtual USB controller
lsmod | grep vhci_hcd                   # should print the module
```

To make the module survive reboots (optional, client side):

```bash
echo vhci_hcd | sudo tee /etc/modules-load.d/vhci_hcd.conf
```

## Daily use

```bash
sudo usbip list -r banach.local                 # list what is shared
sudo usbip attach -r banach.local -b 1-1.4      # attach -> device plugs in on THIS machine
lsusb                                           # verify it appears
sudo usbip detach -r banach.local -b 1-1.4      # graceful release
```

`-b` is the busid shown by the list command.

Both machines must be in the same network (e.g. same Wi-Fi) — the Pi broadcasts
its name `banach.local` itself, so it follows the Pi even when the Pi moves.

## Troubleshooting (Linux client)

| symptom | cause ↔ fix |
|---|---|
| `usbip list` prints `usbip: error: socket connection to server failed` | usbipd not running/port blocked → on the Pi: `wirehub tail` |
| `usbip: error: could not unbind and unmark device on busid` | the device is **in use on the Pi itself** → unuse it there (e.g. unmount) |
| device attached but `dmesg` shows `failed to attach` | client firewall/router block of TCP 3240 or the device got unplugged meanwhile |
| slow transfers | Wi-Fi latency is the limit — big mass-storage reads/writes are the worst case |
| after client reboot device gone | clients don't auto-re-attach — run attach again (or the script below) |

## Convenience: dynamic quick-attach

`scripts/attach_remote.sh` (in this repo) does list → prompt → attach in one go:

```bash
sudo ./attach_remote.sh banach.local            # prints the list, then attach <busid>
sudo ./attach_remote.sh banach.local 1-1.4
```

## Sudo-less `lsusb` note

On some distros non-root `lsusb` already shows names; attach/un-attach always
need root. That is expected.
