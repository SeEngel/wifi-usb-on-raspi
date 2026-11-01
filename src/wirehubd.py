#!/usr/bin/env python3
"""wirehubd - USB/IP auto-export orchestrator for wifi-usb-on-raspi.

Watches /sys/bus/usb/devices and exports (binds to usbip_host) every device
that matches the allowlist in /etc/wirehub/config.json. Runs as root via
systemd; power-on ready without any user login. Status JSON API on loopback
(or LAN, config-gated).
"""
import argparse
import json
import os
import signal
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wirehublib as lib  # noqa: E402

STATE = {"config": None, "quit": False, "lastError": None, "http": None}


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def sync_once():
    """Export every present, allowed, not-yet-bound device (with throttling + no log spam)."""
    cfg = STATE["config"]
    attempts = STATE.setdefault("attemptTime", {})
    errSeen = STATE.setdefault("errorSeen", {})
    now = time.time()
    for busid in lib.usb_locations():
        try:
            attrs = lib.device_attrs(busid)
        except OSError:
            continue  # device vanished mid-scan
        if lib.is_exported(busid):
            errSeen.pop(busid, None)
            continue
        for rule in cfg["allowlist"]:
            if not (rule.get("autoExport", True) and lib.matches(rule, attrs)):
                continue
            # throttle repeat attempts for the same device (errors otherwise spam)
            if now - attempts.get(busid, 0) < 30:
                break
            attempts[busid] = now
            label = attrs["product"] or attrs["vid"] + ":" + attrs["pid"]
            log(f"exporting {busid} '{label}' (rule '{rule['name']}')")
            rc, out = lib.export(busid)
            if rc != 0:
                STATE["lastError"] = out
                if errSeen.get(busid) != out:
                    errSeen[busid] = out
                    log(f"  export FAILED (retry in 30s): {out}")
            else:
                errSeen.pop(busid, None)
                log(f"  export ok: {busid}")
            break


def status_json():
    cfg = STATE["config"]
    devices = []
    for busid in lib.usb_locations():
        try:
            a = lib.device_attrs(busid)
        except OSError:
            continue
        a["exported"] = lib.is_exported(busid)
        devices.append(a)
    return {
        "host": socket.gethostname(),
        "usbipPort": cfg["usbipd"].get("port", 3240),
        "devices": devices,
        "allowlistRules": len(cfg["allowlist"]),
        "lastError": STATE["lastError"],
        "timestamp": time.time(),
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/status", "/"):
            body = json.dumps(status_json()).encode()
        elif path == "/devices":
            body = json.dumps(status_json()["devices"]).encode()
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass  # keep the journal clean


def serve_http():
    api = STATE["config"]["statusApi"]
    if not api.get("enabled", True):
        return
    bind = "0.0.0.0" if api.get("lan") else "127.0.0.1"
    srv = ThreadingHTTPServer((bind, api.get("port", lib.STATUS_PORT_DEFAULT)), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    STATE["http"] = srv
    log(f"status API listening on {bind}:{api.get('port', lib.STATUS_PORT_DEFAULT)}")


def request_stop(signum, frame):
    STATE["quit"] = True


def main():
    ap = argparse.ArgumentParser(description="wirehubd - USB/IP export orchestrator")
    ap.add_argument("--config", default=lib.DEFAULT_CONFIG)
    a = ap.parse_args()
    STATE["config"] = lib.load_config(a.config)
    problems = lib.validate_config(STATE["config"])
    for p in problems:
        log(f"CONFIG WARNING: {p}")
    log(f"started, config={a.config}, allowlist rules={len(STATE['config']['allowlist'])}")
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    serve_http()
    sync_once()
    while not STATE["quit"]:
        time.sleep(2)
        try:
            sync_once()
        except Exception as e:  # keep the daemon alive no matter what
            STATE["lastError"] = str(e)
            log("sync error: " + str(e))
    if STATE["config"].get("detachOnStop", True):
        for busid in lib.usb_locations():
            if lib.is_exported(busid):
                log(f"unexporting on shutdown: {busid}")
                lib.unexport(busid)
    log("stopped")


if __name__ == "__main__":
    main()
