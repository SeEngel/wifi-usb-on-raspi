> Windows client status: **draft in Phase 6** — this is the honest best-effort plan, refined when Sebastian's actual Windows machine is targeted.

# Windows clients (10/11 supported, Windows 7-8.x legacy not)

Two routes to use devices shared by `banach.local` from Windows:

| Route | Pro | Con |
|---|---|---|
| **A: usbip-win** (native driver, https://github.com/cezanne/usbip-win) | device appears in raw Windows (Device Manager) | community driver, must allow-list the test-signed driver |
| **B: WSL2** (Windows includes the Linux `usbip` client inside WSL) | safe/reliable, official tooling | device visible inside WSL2, not to Windows X11 apps |

Route B is straightforward:

```powershell
wsl --install                      # once
wsl
sudo apt install usbip -y          # inside WSL Ubuntu
sudo modprobe vhci_hcd && sudo usbip list -r banach.local && sudo usbip attach -r banach.local -b 1-1.4
```

Route A post-install binary and instructions ship as a `scripts/win/README` note in Phase 6 with the exact validated binaries — untill then, @todo is left open for now in this space.
