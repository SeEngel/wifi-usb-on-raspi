"""Shared helpers for wirehubd (daemon) and wirehub (CLI). Part of wifi-usb-on-raspi."""
import json
import subprocess
from pathlib import Path

SYSFS_USB = Path("/sys/bus/usb/devices")
USBIP_HOST_DRIVER = Path("/sys/bus/usb/drivers/usbip_host")
DEFAULT_CONFIG = "/etc/wirehub/config.json"
STATUS_PORT_DEFAULT = 22824


def load_config(path):
    """Read + normalize the wirehub config JSON."""
    with open(path) as f:
        cfg = json.load(f)
    allow = []
    for i, rule in enumerate(cfg.get("allowlist", [])):
        if not isinstance(rule, dict):
            raise ValueError(f"allowlist entry {i} is not an object")
        rule.setdefault("name", f"rule_{i}")
        rule["vid"] = str(rule.get("vid") or "").strip().lower() or None
        rule["pid"] = str(rule.get("pid") or "").strip().lower() or None
        ser = str(rule.get("serial") or "").strip()
        rule["serial"] = ser or None
        rule.setdefault("autoExport", True)
        allow.append(rule)
    cfg["allowlist"] = allow
    cfg.setdefault("usbipd", {"port": 3240})
    api = cfg.setdefault("statusApi", {})
    api.setdefault("enabled", True)
    api.setdefault("lan", False)
    api.setdefault("port", STATUS_PORT_DEFAULT)
    cfg.setdefault("detachOnStop", True)
    return cfg


def validate_config(cfg):
    """Return a list of human-readable problems (empty list = OK)."""
    problems = []
    for r in cfg.get("allowlist", []):
        if not (r["vid"] or r["pid"] or r["serial"]):
            problems.append(f"rule '{r['name']}' has no vid/pid/serial -> would match EVERYTHING")
    return problems


def usb_locations():
    """All present top-level USB devices (busids), excluding virtual vhci devices."""
    out = []
    for d in SYSFS_USB.glob("*"):
        if ":" in d.name:
            continue  # interface dirs, not devices
        if not ((d / "idVendor").exists() and (d / "idProduct").exists()):
            continue
        try:
            resolved = str(d.resolve())
        except OSError:
            resolved = ""
        if "vhci" in resolved:
            continue  # client-side virtual device (vhci) - nothing to export here
        out.append(d.name)
    return sorted(out)


def device_attrs(busid):
    """Read idVendor/idProduct/serial/product from sysfs (raises if device vanished)."""
    d = SYSFS_USB / busid
    attrs = {
        "busid": busid,
        "vid": (d / "idVendor").read_text().strip().lower(),
        "pid": (d / "idProduct").read_text().strip().lower(),
        "serial": None,
        "product": None,
        "manufacturer": None,
    }
    sp = d / "serial"
    if sp.exists():
        attrs["serial"] = sp.read_text().strip()
    pp = d / "product"
    if pp.exists():
        attrs["product"] = pp.read_text().strip()
    mp = d / "manufacturer"
    if mp.exists():
        attrs["manufacturer"] = mp.read_text().strip()
    return attrs


def matches(rule, attrs):
    """True when every non-wildcard rule field equals the device attrs."""
    if rule["vid"] and rule["vid"] != attrs["vid"]:
        return False
    if rule["pid"] and rule["pid"] != attrs["pid"]:
        return False
    if rule["serial"] and rule["serial"] != attrs["serial"]:
        return False
    return True


def bound_busids():
    """Busids currently bound to usbip_host (== exported)."""
    if not USBIP_HOST_DRIVER.is_dir():
        return set()
    out = set()
    for entry in USBIP_HOST_DRIVER.iterdir():
        n = entry.name
        if n in ("bind", "unbind", "uevent", "new_id", "remove_id", "module"):
            continue
        out.add(n.split(":")[0])
    return out


def is_exported(busid):
    """True if this exact device's sysfs driver is usbip_host (reliable single-device check)."""
    drv = SYSFS_USB / busid / "driver"
    if not drv.exists():
        return False
    try:
        return drv.resolve().name == "usbip_host"
    except OSError:
        return False


def run_usbip(*args):
    """Run the usbip tool; returns (returncode, combined_output)."""
    p = subprocess.run(["usbip", *args], capture_output=True, text=True, timeout=60)
    return p.returncode, (p.stdout + p.stderr).strip()


def export(busid):
    """Bind a device to usbip_host -> it becomes exportable via usbipd."""
    return run_usbip("bind", "-b", busid)


def unexport(busid):
    """Unbind -> device returns to local use on this machine."""
    return run_usbip("unbind", "-b", busid)
