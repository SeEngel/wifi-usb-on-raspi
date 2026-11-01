# Plan — Wi-Fi USB on Raspberry Pi

**Project:** `wifi-usb-on-raspi` · **Pi:** `banach` (Raspberry Pi 4, Debian 12 bookworm, aarch64, kernel 6.12.20)
**Goal:** Plug USB devices into the Raspberry Pi — use them on *other* devices over Wi-Fi **as if they were plugged in locally**.
**Status of this file:** The master plan. Checklists are worked off top-down. Everything new gets checked here.

---

## 1. The Decision (Strategy — read this first)

### What technology do we use?

**USB/IP (`usbip`)** — Linux-kernel-native protocol for sharing USB devices over a TCP/IP network.

| Option | Verdict | Why |
|---|---|---|
| **USB/IP (kernel)** | ✅ **CHOSEN** | Standard since kernel 3.17. Protocol runs **in the kernel**, so performance beats any userspace hack. Works for real device classes (HID, serial, mass storage). Client attach feels like a local USB plug. |
| Rust/Python **userspace reimplementation** | ❌ | Reimplementing USB descriptors/URB transport in userspace is months of work for zero benefit — the kernel already does it. |
| **Rust wrapper** for tooling | ⚪ optional | Not needed. The hot part is kernel-side; the daemon is trivial glue → **Python is enough, simpler to maintain**. |
| Windows-side server (`usbipd-win`) | ❌ | Reverse direction: shares *Windows* USB into WSL. Doesn't help us. |
| Network tunneling of serial only (`ser2net`) | ❌ | Only covers serial ports, not "USB device as a whole". |

**Final software choice:** Python orchestration daemon on top of the kernel's `usbip` stack. Plain, boring, correct.

### System components (to be built)

```
┌────────────────────── Raspberry Pi "banach" ─────────────────────┐
│   USB devices (Arduino, sticks, ...)                             │
│        │ /sys/bus/usb                                            │
│   usbip_host kernel module  ← kernel handles the USB-IP protocol │
│        │                                                         │
│   usbipd (from Debian pkg, TCP :3240)  ← listens for clients     │
│        │ controlled by                                           │
│   wirehubd (Python daemon, OUR code)                             │
│     • hotplug watcher (pyudev): new USB device → auto-export     │
│     • reads config/wirehub.json (which devices may be shared)    │
│     • status JSON API                                            │
│        │                                                         │
│   wirehub   (little CLI: status / list / export / unbind)        │
│   systemd units (boot-ready without any login/bashrc)            │
│   avahi: mDNS  → reachable as  banach.local  in EVERY network    │
└──────────────────────────────────────────────────────────────────┘
                 ▲
                 │  USB/IP over Wi-Fi (TCP 3240)
┌────────────────┴───────────────┐
│  Client device (Linux / Win/WSL)│
│  sudo usbip attach -r banach.local -b <busid>  ← device appears │
│  as local USB (lsusb shows it)                                   │
└─────────────────────────────────┘
```

### Honest constraints (no surprise later)

1. **Client OS support:**
   - **Linux:** full support, `usbip` client is built into kernel (best case).
   - **Windows 11 / Windows 10:** two routes — **native client driver** (`usbip-win`, community, best-effort) or **WSL2** (Windows ships a `usbip` client there; reliable). Plan documents both.
   - **Android:** needs root — *not targeted* (honest).
   - **macOS:** no kernel client — *not supported* (honest).
2. **Exclusive access:** while a device is attached by a client, the Pi's local access is detached (that is inherently how USB/IP works). Detach returns it.
3. **Security:** USB/IP has **no encryption/auth** by design → run only in trusted home Wi-Fi. We add an optional host firewall rule limiting port 3240 to the local network.
4. **Speed:** fine for HID, USB-serial (Arduino/ESP32!), small flash sticks. Big mass-storage transfers limited by Wi-Fi latency (~10–40 MB/s best case). USB video cameras may stutter on weak Wi-Fi.
5. **Which device classes work well:** keyboard/mouse ✔, USB-serial ✔ (main use case for the `robot` project), flash drives ✔ (slower), printers ✖/border, webcams ⚠.

### Reaching the Pi — stable address

- The Pi is **always reachable as `banach.local`** (mDNS via `avahi-daemon`, already active). The `.local` name is **broadcast by the Pi itself**, so it **survives moving the Pi to a different Wi-Fi** — as long as the client is in the *same* network as the Pi at that time.
- Windows 11 handles mDNS natively; older Windows 10: mDNS works since 21H2 or via the `Bonjour` route (documented later).
- Belt-and-braces: `docs/` will show how to set a **DHCP reservation** (router) so the IP also stays stable — then `ssh`/clients can alternatively use the IP.
- Service port: **TCP 3240** (`usbipd` default). Signature text for the status call: `usbip list -r banach.local`.

### Boot readiness: systemd — and NOT bashrc (corrected 2026-11-01)

Sebastian's correction is right: a bashrc hook **cannot** make software run at power-on (bashrc only executes when a *user interactively logs in* — which nobody will do on a headless Pi). It was planned as convenience only and is now **removed from the project entirely**. The boot mechanism is **exclusively systemd**:

- `usbipd.service` — kernel-facing USB/IP server, listens on TCP 3240
- `wirehubd.service` — our orchestrator; after boot it automatically shares every allowed device (no login, no monitor needed)

Both units are `WantedBy=multi-user.target` with `Restart=always` → **power on → fully ready within ~30 s, headless, no screen, no login**. The CLI is installed system-wide to `/usr/local/bin/wirehub` (which is on PATH by default — no bashrc hack needed).

---

## 2. Phases & Checklists

### Phase 0 — Repository scaffolding
- [ ] 0.1 Directory layout inside this repo:
      `src/` (wirehubd + wirehub CLI), `config/`, `scripts/`, `systemd/`, `docs/`, `tests/`,
      plus `install.sh`, `uninstall.sh`, `README.md`, `Plan.md`
- [ ] 0.2 `.gitignore` (pycache, venv, backups)
- [ ] 0.3 Git identity on `banach` checked/available; commit plan
- [ ] 0.4 `LICENSE` (MIT) + copyright line
- [x] 0.5 `Plan.md` created (this file)

### Phase 1 — Feasibility spike (raw usbip, by hand)
- [ ] 1.1 Install packages on Pi: `usbip-utils` + kernel modules (`linux-modules-*-rpi` already have them; verify `apt-cache usbip`)
- [ ] 1.2 Load modules `usbip_core`, `usbip_host`; make persistent via `/etc/modules-load.d/wirehub.conf`
- [ ] 1.3 Start `usbipd`; list devices (`usbip list -l`); bind one test device (e.g. nothing critical — use a stick or the hub first)
- [ ] 1.4 Client attach test from a Linux box (and loopback test from banach itself using `vhci_hcd`)
- [ ] 1.5 Record results matrix: which of Sebastian's devices attach cleanly (Arduino/serial, mouse, stick)
- [ ] 1.6 Document first-lesson findings (Cadence: every oddity → repo `docs/notes.md` + skill LOG)
- [ ] 1.7 Client-test execution: loopback on banach (`usbip attach -r banach.local`) → stick appears in `lsusb` of the attached (v)hci — JARVIS container noted impossible (see Q1)

### Phase 2 — Configuration model
- [ ] 2.1 `config/wirehub.json` schema:
      `allowedDevices[] {busid?, vid, pid, serial, name, autoExport}`, `httpStatusApi {enabled, lan}`, `logLevel`
- [ ] 2.2 Schema validation (`jsonschema`) + config example file
- [ ] 2.3 `wirehub config check` subcommand

### Phase 3 — Daemon `wirehubd` (Python)
- [ ] 3.1 Core: pyudev hotplug monitor → bind+export according to config (allowlist rules)
- [ ] 3.2 Startup resync: bind/export everything allowed that is already plugged (survives reboot without client)
- [ ] 3.3 Status JSON API (`GET /status`, `GET /devices`) — default **localhost only**, LAN switchable in config
- [ ] 3.4 Logging to systemd journal, log levels, rotation-friendly
- [ ] 3.5 Graceful stop: detach-export on SIGTERM, *never* yank a device a client is actively using (configurable)
- [ ] 3.6 Unit test suite (daemon logic mocked via fake `usbip` command injection)
- [ ] 3.7 CLI `wirehub`: `status`, `list`, `export [busid]`, `unexport [busid]`, `tail` (journal follow)

### Phase 4 — Boot integration (systemd + optional bashrc)
- [ ] 4.1 `systemd/usbipd.service` shipped (standalone kernel daemon)
- [ ] 4.2 `systemd/wirehubd.service` shipped (our Python daemon, `After=network-online.target`, `Restart=always`)
- [ ] 4.3 Real power-cycle test on the Pi: boot → within ~30 s everything allowed is exported, no login needed
- [ ] 4.4 CLI installed to `/usr/local/bin/wirehub` — **no bashrc hook (removed by design decision 2026-11-01; systemd is the sole boot mechanism)**

### Phase 5 — Install & Uninstall scripts (the *one-liner* requirement)
- [ ] 5.1 `install.sh`:
      • `apt-get install` needed packages
      • writes `modules-load.d`, copies daemon+CLI, writes config if missing (asks before overwriting)
      • installs+enables systemd units, prints a summary **including the exact reachability recipes** (`banach.local:3240`)
- [ ] 5.2 Flags: `--no-apt` (offline), `--config path`, idempotent (re-run = no-op)
- [ ] 5.3 `uninstall.sh`: stop+disable units, remove files, remove module persistence, **keep config backup** (`/var/backups/wirehub/`), optional `--purge` also removes packages
- [ ] 5.4 Both scripts tested twice in a row on the real Pi (install → uninstall → install → install again)
- [ ] 5.5 Each script's output printed exactly once, last line = "READY" or "REMOVED" + address

### Phase 6 — Client onboarding (the "how do I USE it" requirement)
- [ ] 6.1 `docs/clients-linux.md`: for any Debian/Ubuntu box — install `usbip`, attach one-liner, auto-attach helper
- [ ] 6.2 `scripts/attach_remote.sh <host> [busid]`: helper: list then attach; usable from any Linux client
- [ ] 6.3 `docs/clients-windows.md`: route A native `usbip-win` (steps + known pitfalls), route B WSL2 (recommended if route A fails)
- [ ] 6.4 README cheat sheet (copy-paste block) + Troubleshooting table (`connection refused`, stale `/dev`, firewall 3240, `device busy`)
- [ ] 6.5 Firewall recipe on the Pi (optional): nftables/ufw rule = port 3240 only from `192.168.x.0/24` / home subnets
- [ ] 6.6 End-to-end demo documented: Arduino plugged into `banach`, appears on client `lsusb` and in `dmesg` (optional screenshots as proof)

### Phase 7 — Hardening & polish
- [ ] 7.1 Network move test: Pi into 2nd Wi-Fi → client reaches it again under same name (`banach.local`) — the requirement you set
- [ ] 7.2 mDNS advertisement `_usbip._tcp` (avahi publish) so future clients auto-discover the Pi
- [ ] 7.3 Documentation: accurate `README.md` (EN), moved Plan checkboxes up-to-date
- [ ] 7.4 Push everything to GitHub
- [ ] 7.5 Fresh-eyes test: a new reader follows only the README → it works without anyone having to ask

### Phase 8 — Done-Definitions (Definition of Done for the whole project)
- [ ] 8.1 `bash <(command from README or curl) install.sh`-style one-liner install documented
- [ ] 8.2 Uninstall leaves the Pi clean (shell history diff = no leftovers)
- [ ] 8.3 All repo docs in English (markdown), Plan.md fully checked
- [ ] 8.4 New `skills/wifi-usb-raspi` (JARVIS side) captures all *lessons* (hostaddress, module names, attach commands, pitfalls)

---

## 3. Rollout order & time-shape (rough)

| Step | What | Rough effort |
|---|---|---|
| R1 | Phase 0–1 (scaffold + prove usbip works by hand) | one session |
| R2 | Phase 2–3 (config + daemon) | one session |
| R3 | Phase 4–5 (boot + install/uninstall) | one session |
| R4 | Phase 6 (clients + doc) | one session |
| R5 | Phase 7–8 (hardening + push) | half session |

Each rollout step ends with: **plan checkboxes ticked + tested on banach before moving on**.

---

## 4. Open questions (to close before/while implementing)

- [x] Q1 **Test client** (resolved 2026-11-01): the J.A.R.V.I.S. agent OS (proot container on the Pixel) **cannot** act as a USB/IP client — no kernel-module access in the container (no `vhci_hcd`, no `/dev/bus/usb`). Accepted strategy: **loopback test on banach first** (`banach` ↔ `banach.local` proves server *and* client side of the stack), real Linux-PC client later, Windows (usbip-win / WSL2) documented in Phase 6 on demand.
- [x] Q2 **Test device** (resolved 2026-11-01): a spare USB stick is available — Sebastian plugs it into banach on request (the moment wirehubd is ready).
- [ ] Q3 Firewall: keep port 3240 fully LAN-open or restricted-to-subnet? (default goal = restricted; decide in Phase 7)

---

## 5. Changelog of this plan

- 2026-11-01 — Plan.md authored (v1): strategy = kernel USB/IP + Python daemon `wirehubd`; phases 0–8 defined.
- 2026-11-01 (v2) — Sebastian's correction applied: **bashrc fully removed from concept**; boot readiness is systemd-only (headless power-on requirement). Test-client strategy fixed (Q1: loopback on banach; JARVIS container technically impossible). Q2 resolved (stick plugged on demand).
