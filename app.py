import time
import threading
import json
import os
import ipaddress
from pathlib import Path

from backend.database import GNBDatabase
from backend.gnb_monitor import (
    start_gnb_monitor_thread,
    get_gnb,
    is_gnb_starting,
    stop_gnb_monitor
)

from flask import (
    Flask,
    render_template,
    jsonify,
    request
)

app = Flask(__name__)

db = GNBDatabase()

# =========================================================
# gNB Pool
# =========================================================

# Existing gNBs remain configured at startup.
DEFAULT_GNBS = ["10.255.174.7", "10.255.175.105"]
GNB_CONFIG_FILE = Path(__file__).resolve().parent / "database" / "gnb_ips.json"
GNB_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
GNB_POOL_LOCK = threading.RLock()

# Credentials are shared across gNBs. Override through environment variables.
GNB_USERNAME = os.environ.get("GNB_USERNAME", "ognb")
GNB_PASSWORD = os.environ.get("GNB_PASSWORD", "ognb123")
GNB_SSH_PORT = int(os.environ.get("GNB_SSH_PORT", "22"))

# Only permit gNB management networks. Override via comma-separated CIDRs.
ALLOWED_GNB_NETWORKS = [
    ipaddress.ip_network(item.strip())
    for item in os.environ.get(
        "ALLOWED_GNB_NETWORKS", "10.255.174.0/24,10.255.175.0/24"
    ).split(",") if item.strip()
]


def validate_gnb_ip(value):
    try:
        addr = ipaddress.ip_address(value)
    except (ValueError, TypeError):
        return None
    if addr.version != 4 or not any(addr in network for network in ALLOWED_GNB_NETWORKS):
        return None
    return str(addr)


def load_gnb_ips():
    ips = list(DEFAULT_GNBS) if not GNB_CONFIG_FILE.exists() else []
    if GNB_CONFIG_FILE.exists():
        try:
            saved = json.loads(GNB_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, list):
                ips.extend(saved)
        except (OSError, ValueError) as error:
            print(f"[gNB Pool] Failed to load saved IPs: {error}")
    return list(dict.fromkeys(ip for value in ips if (ip := validate_gnb_ip(value))))


def save_gnb_ips():
    # Called while holding GNB_POOL_LOCK.
    temp = GNB_CONFIG_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(list(GNB_POOL), indent=2), encoding="utf-8")
    temp.replace(GNB_CONFIG_FILE)


GNB_POOL = {
    ip: {"username": GNB_USERNAME, "password": GNB_PASSWORD, "port": GNB_SSH_PORT}
    for ip in load_gnb_ips()
}


# RU/CC configuration is independent for each gNB.
RU_CONFIG_FILE = GNB_CONFIG_FILE.parent / "ru_config.json"
RU_CONFIG_LOCK = threading.RLock()


def read_ru_config():
    try:
        saved = json.loads(RU_CONFIG_FILE.read_text(encoding="utf-8"))
        return saved if isinstance(saved, dict) else {}
    except (OSError, ValueError):
        return {}


def get_ru_config(ip):
    with RU_CONFIG_LOCK:
        config = read_ru_config().get(ip, {})
    ru_count = config.get("ru_count", 1)
    cc_per_ru = config.get("cc_per_ru", 3)
    if type(ru_count) is not int or not 1 <= ru_count <= 4:
        ru_count = 1
    if type(cc_per_ru) is not int or not 1 <= cc_per_ru <= 3:
        cc_per_ru = 3
    return {"ru_count": ru_count, "cc_per_ru": cc_per_ru}


@app.route("/api/ru-config", methods=["GET", "PUT"])
def ru_config_api():
    ip = request.args.get("ip")
    with GNB_POOL_LOCK:
        if ip not in GNB_POOL:
            return jsonify({"error": "Unknown gNB IP"}), 400
    if request.method == "GET":
        return jsonify({"ip": ip, **get_ru_config(ip)})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Expected JSON object"}), 400
    ru_count = payload.get("ru_count")
    cc_per_ru = payload.get("cc_per_ru")
    if (type(ru_count) is not int or not 1 <= ru_count <= 4
            or type(cc_per_ru) is not int or not 1 <= cc_per_ru <= 3):
        return jsonify({"error": "ru_count must be 1..4 and cc_per_ru 1..3"}), 400
    with RU_CONFIG_LOCK:
        saved = read_ru_config()
        saved[ip] = {"ru_count": ru_count, "cc_per_ru": cc_per_ru}
        try:
            temp = RU_CONFIG_FILE.with_suffix(".tmp")
            temp.write_text(json.dumps(saved, indent=2), encoding="utf-8")
            temp.replace(RU_CONFIG_FILE)
        except OSError as error:
            return jsonify({"error": str(error)}), 500
    return jsonify({"ip": ip, **saved[ip]})


@app.route("/api/gnbs", methods=["GET"])
def list_gnbs():
    with GNB_POOL_LOCK:
        ips = list(GNB_POOL)
    return jsonify({"gnbs": ips})


@app.route("/api/gnbs", methods=["POST"])
def add_gnb():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Expected JSON object"}), 400
    ip = validate_gnb_ip(payload.get("ip"))
    if ip is None:
        return jsonify({"error": "Invalid IP or IP outside allowed gNB networks"}), 400

    with GNB_POOL_LOCK:
        if ip in GNB_POOL:
            # An existing IP is not added again. If a previous connection failed,
            # a new POST may retry; the monitor layer prevents duplicate workers.
            existing = True
        else:
            existing = False
            GNB_POOL[ip] = {
                "username": GNB_USERNAME, "password": GNB_PASSWORD, "port": GNB_SSH_PORT
            }
            try:
                save_gnb_ips()
            except OSError as error:
                del GNB_POOL[ip]
                return jsonify({"error": f"Unable to save gNB list: {error}"}), 500
        config = GNB_POOL[ip].copy()

    if not existing or (get_gnb(ip) is None and not is_gnb_starting(ip)):
        start_gnb_monitor_thread(
            ip_address=ip,
            username=config["username"],
            password=config["password"],
            port=config["port"]
        )
    return jsonify({"ip": ip, "added": not existing, "status": "connecting"}), (201 if not existing else 200)


@app.route("/api/gnbs/<ip>", methods=["DELETE"])
def remove_gnb(ip):
    ip = validate_gnb_ip(ip)
    if ip is None:
        return jsonify({"error": "Invalid gNB IP"}), 400
    with GNB_POOL_LOCK:
        if ip not in GNB_POOL:
            return jsonify({"error": "gNB not found"}), 404
        # Keep the configuration until stop has actually succeeded.
        success, message = stop_gnb_monitor(ip)
        if not success:
            return jsonify({"error": message}), 409
        config = GNB_POOL.pop(ip)
        try:
            save_gnb_ips()
        except OSError as exc:
            GNB_POOL[ip] = config
            return jsonify({"error": f"Stopped, but unable to save list: {exc}"}), 500
    return jsonify({"ip": ip, "removed": True, "stopped": True})


# =========================================================
# gNB connectiong
# =========================================================
@app.route("/api/status")
def gnb_status():

    ip = request.args.get("ip")

    if ip not in GNB_POOL:
        return jsonify({
            "ip": ip,
            "connected": False,
            "error": "Unknown gNB IP"
        }), 400

    gnb = get_gnb(ip)

    if gnb is None:
        return jsonify({
            "ip": ip,
            "connected": False,
            "connecting": is_gnb_starting(ip),
            "l1_uptime": "Unknown"
        })

    try:
        transport = gnb.ssh_client.get_transport()

        connected = (
            transport is not None
            and transport.is_active()
            and transport.is_authenticated()
        )

    except Exception:
        connected = False

    return jsonify({
        "ip": ip,
        "connected": connected,
        "connecting": is_gnb_starting(ip),
        "l1_uptime": gnb.get_uptime() if connected else "Unknown"
    })


# =========================================================
# Dashboard
# =========================================================

@app.route("/")
def index():
    return render_template(
        "dashboard.html"
    )


# =========================================================
# Throughput API
# =========================================================

@app.route("/api/throughput")
def throughput():
    ip = request.args.get(
        "ip"
    )

    duration = request.args.get(
        "range",
        "10m"
    )

    # -----------------------------------------------------
    # 確認 IP 是否在 gNB Pool
    # -----------------------------------------------------

    if ip not in GNB_POOL:
        return jsonify({
            "error": "Unknown gNB IP",
            "ip": ip
        }), 400

    # -----------------------------------------------------
    # 目前 database 還沒有按照 IP 分開
    #
    # 這裡先保留你原本的 database 查詢
    # -----------------------------------------------------

    config = get_ru_config(ip)
    try:
        ru = int(request.args.get("ru", "1"))
    except ValueError:
        return jsonify({"error": "Invalid RU"}), 400
    if not 1 <= ru <= config["ru_count"]:
        return jsonify({"error": "RU outside configured range"}), 400
    start_cell = (ru - 1) * config["cc_per_ru"]
    cells = []
    for cc in range(config["cc_per_ru"]):
        cell_id = start_cell + cc
        cells.append({
            "cc": cc,
            "cell_id": cell_id,
            "dl": db.get_throughput_history(
                gnb_ip=ip, duration=duration, cell_id=cell_id,
                column="dl_throughput"
            ),
            "ul": db.get_throughput_history(
                gnb_ip=ip, duration=duration, cell_id=cell_id,
                column="ul_throughput"
            )
        })
    return jsonify({"ip": ip, "ru": ru, "cc_per_ru": config["cc_per_ru"], "cells": cells})


# =========================================================
# Database Cleanup
# =========================================================

def cleanup():
    while True:
        db.delete_old_data()

        time.sleep(
            86400
        )


# =========================================================
# Logs API
# =========================================================

@app.route("/api/logs")
def logs():
    ip = request.args.get(
        "ip"
    )

    # -----------------------------------------------------
    # 確認 IP 是否在 gNB Pool
    # -----------------------------------------------------

    if ip not in GNB_POOL:
        return jsonify({
            "error": "Unknown gNB IP",
            "ip": ip
        }), 400

    # -----------------------------------------------------
    # 取得指定 gNB
    # -----------------------------------------------------

    gnb = get_gnb(
        ip
    )

    if gnb is None:
        return jsonify({

            "netconf": [],
            "rumanager": []

        })

    return jsonify({

        "netconf":
            gnb.get_netconf_logs(),

        "rumanager":
            gnb.get_rumanager_logs()

    })


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    # =====================================================
    # Start all gNB monitors
    # =====================================================

    for ip, config in list(GNB_POOL.items()):
        print(
            "[gNB Pool] "
            f"Starting monitor: {ip}"
        )

        start_gnb_monitor_thread(

            ip_address=ip,

            username=config["username"],

            password=config["password"],

            port=config["port"]

        )

    # =====================================================
    # Start database cleanup
    # =====================================================

    threading.Thread(

        target=cleanup,

        daemon=True

    ).start()

    # =====================================================
    # Start Flask
    # =====================================================

    app.run(

        host="0.0.0.0",

        port=5000,
        use_reloader=False

    )

"""
=========================================================
Available gNB servers
=========================================================

10.255.174.7
10.255.174.239
10.255.175.129
10.255.175.210
10.255.175.105
10.255.174.135

=========================================================
"""
