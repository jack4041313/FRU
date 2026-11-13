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
    stop_gnb_monitor,
    is_gnb_starting
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

# No devices are automatically loaded or monitored on application startup.
DEFAULT_GNBS = []
GNB_CONFIG_FILE = Path(__file__).resolve().parent / "database" / "gnb_ips.json"
GNB_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
GNB_POOL_LOCK = threading.RLock()

# Credentials are shared across gNBs. Override through environment variables.
GNB_USERNAME = os.environ.get("GNB_USERNAME", "ognb")
GNB_PASSWORD = os.environ.get("GNB_PASSWORD", "ognb123")
GNB_SSH_PORT = int(os.environ.get("GNB_SSH_PORT", "22"))
PS2400_USERNAME = "padmin"
PS2400_PASSWORD = "Pega@2025"
PS2400_SSH_PORT = int(os.environ.get("PS2400_SSH_PORT", "22"))

# Only permit gNB management networks. Override via comma-separated CIDRs.
ALLOWED_GNB_NETWORKS = [
    ipaddress.ip_network(item.strip())
    for item in os.environ.get(
        "ALLOWED_GNB_NETWORKS", "10.255.174.0/24,10.255.175.0/24"
    ).split(",") if item.strip()
]


def parse_gnb_input(value):
    """Return (real SSH IPv4 address, device type), or (None, None)."""
    if not isinstance(value, str):
        return None, None
    value = value.strip()
    device_type = "PS2400" if value.upper().startswith("PS2400-") else "STANDARD"
    address = value[7:] if device_type == "PS2400" else value
    try:
        addr = ipaddress.ip_address(address)
    except (ValueError, TypeError):
        return None, None
    if addr.version != 4 or not any(addr in network for network in ALLOWED_GNB_NETWORKS):
        return None, None
    return str(addr), device_type


def validate_gnb_ip(value):
    ip, _ = parse_gnb_input(value)
    return ip


def load_gnb_entries():
    """Start with an empty device list on every Flask launch.

    Previously saved entries are deliberately not restored: devices only
    become active after the user explicitly adds them through the UI.
    """
    return {}


GNB_DEVICE_TYPES = load_gnb_entries()


def display_gnb_name(ip):
    return f"PS2400-{ip}" if GNB_DEVICE_TYPES.get(ip) == "PS2400" else ip


def save_gnb_ips():
    # Called while holding GNB_POOL_LOCK.
    temp = GNB_CONFIG_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps([display_gnb_name(ip) for ip in GNB_POOL], indent=2), encoding="utf-8")
    temp.replace(GNB_CONFIG_FILE)


GNB_POOL = {
    ip: {"username": GNB_USERNAME, "password": GNB_PASSWORD, "port": GNB_SSH_PORT}
    for ip in GNB_DEVICE_TYPES
}


@app.route("/api/gnbs", methods=["GET"])
def list_gnbs():
    with GNB_POOL_LOCK:
        ips = list(GNB_POOL)
    return jsonify({"gnbs": ips, "labels": {ip: display_gnb_name(ip) for ip in ips}})


@app.route("/api/gnbs", methods=["POST"])
def add_gnb():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Expected JSON object"}), 400
    ip, device_type = parse_gnb_input(payload.get("ip"))
    if ip is None:
        return jsonify({"error": "Invalid IP or IP outside allowed gNB networks"}), 400

    with GNB_POOL_LOCK:
        if ip in GNB_POOL:
            # An existing IP is not added again. If a previous connection failed,
            # a new POST may retry; the monitor layer prevents duplicate workers.
            existing = True
        else:
            existing = False
            GNB_DEVICE_TYPES[ip] = device_type
            GNB_POOL[ip] = {
                "username": PS2400_USERNAME if device_type == "PS2400" else GNB_USERNAME,
                "password": PS2400_PASSWORD if device_type == "PS2400" else GNB_PASSWORD,
                "port": PS2400_SSH_PORT if device_type == "PS2400" else GNB_SSH_PORT,
                "device_type": device_type
            }
            try:
                save_gnb_ips()
            except OSError as error:
                del GNB_POOL[ip]
                GNB_DEVICE_TYPES.pop(ip, None)
                return jsonify({"error": f"Unable to save gNB list: {error}"}), 500
        if existing and GNB_DEVICE_TYPES.get(ip) != device_type:
            return jsonify({"error": "Device type cannot change while added; remove it first"}), 409
        config = GNB_POOL[ip].copy()

    if not existing or get_gnb(ip) is None:
        start_gnb_once(ip, config)
    return jsonify({"ip": ip, "label": display_gnb_name(ip), "device_type": GNB_DEVICE_TYPES[ip], "added": not existing, "status": "connecting"}), (201 if not existing else 200)



# Guard against duplicate SSH monitor threads during repeated Add clicks.
GNB_MONITOR_THREADS = {}
GNB_MONITOR_THREADS_LOCK = threading.Lock()

def start_gnb_once(ip, config):
    with GNB_MONITOR_THREADS_LOCK:
        existing = GNB_MONITOR_THREADS.get(ip)
        if existing is not None and existing.is_alive():
            return existing
        thread = start_gnb_monitor_thread(
            ip_address=ip, username=config["username"],
            password=config["password"], port=config["port"],
            device_type=config.get("device_type", "STANDARD")
        )
        GNB_MONITOR_THREADS[ip] = thread
        return thread

# Manual SSH reconnect for one configured gNB; never reconnect other gNBs.
GNB_RECONNECTING = set()
GNB_RECONNECT_LOCK = threading.Lock()

@app.route("/api/gnbs/<ip>/reconnect", methods=["POST"])
def reconnect_gnb(ip):
    ip = validate_gnb_ip(ip)
    if ip is None:
        return jsonify({"error": "Invalid gNB IP"}), 400
    with GNB_POOL_LOCK:
        config = GNB_POOL.get(ip)
        if config is None:
            return jsonify({"error": "gNB is not configured"}), 404
        config = config.copy()
    with GNB_RECONNECT_LOCK:
        if ip in GNB_RECONNECTING or is_gnb_starting(ip):
            return jsonify({"error": "gNB is already reconnecting"}), 409
        gnb = get_gnb(ip)
        if gnb is not None:
            try:
                transport = gnb.ssh_client.get_transport()
                if transport and transport.is_active() and transport.is_authenticated():
                    return jsonify({"error": "gNB is already connected"}), 409
            except Exception:
                pass
        GNB_RECONNECTING.add(ip)

    def worker():
        try:
            success, message = stop_gnb_monitor(ip)
            if not success:
                print(f"[Reconnect][{ip}] Cleanup failed: {message}")
                return
            # Respect Remove gNB while old workers are being cleaned up.
            with GNB_POOL_LOCK:
                if ip not in GNB_POOL:
                    return
                start_gnb_once(ip, config)
        except Exception as exc:
            print(f"[Reconnect][{ip}] Failed: {exc}")
        finally:
            with GNB_RECONNECT_LOCK:
                GNB_RECONNECTING.discard(ip)

    threading.Thread(target=worker, daemon=True, name=f"Reconnect-{ip}").start()
    return jsonify({"ip": ip, "status": "reconnecting"}), 202


@app.route("/api/gnbs/<ip>", methods=["DELETE"])
def remove_gnb(ip):
    ip = validate_gnb_ip(ip)
    if ip is None:
        return jsonify({"error": "Invalid gNB IP"}), 400
    with GNB_POOL_LOCK:
        if ip not in GNB_POOL:
            return jsonify({"error": "gNB not found"}), 404
        success, message = stop_gnb_monitor(ip)
        if not success:
            return jsonify({"error": message}), 409
        config = GNB_POOL.pop(ip)
        device_type = GNB_DEVICE_TYPES.pop(ip, "STANDARD")
        try:
            save_gnb_ips()
        except OSError as exc:
            GNB_POOL[ip] = config
            GNB_DEVICE_TYPES[ip] = device_type
            return jsonify({"error": f"Stopped, but unable to save list: {exc}"}), 500
    with GNB_MONITOR_THREADS_LOCK:
        GNB_MONITOR_THREADS.pop(ip, None)
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
            "reconnecting": ip in GNB_RECONNECTING or is_gnb_starting(ip)
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
        "ue_count": getattr(gnb, "ue_count", None) if connected else None,
        "device_type": GNB_DEVICE_TYPES.get(ip, "STANDARD"),
        "l1_uptime": gnb.get_uptime() if connected else "Unknown",
        "reconnecting": ip in GNB_RECONNECTING or is_gnb_starting(ip)
    })


# =========================================================
# Dashboard
# =========================================================

@app.route("/")
def index():
    return render_template(
        "dashboard.html"
    )


# RU count and CC configuration, persisted separately for each gNB.
RU_CONFIG_FILE = Path(__file__).resolve().parent / "database" / "ru_config.json"
RU_CONFIG_LOCK = threading.RLock()

def read_ru_configs():
    try:
        data = json.loads(RU_CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

@app.route("/api/ru-config", methods=["GET", "PUT"])
def ru_config():
    ip = request.args.get("ip")
    if ip not in GNB_POOL:
        return jsonify({"error": "Unknown gNB IP"}), 400
    with RU_CONFIG_LOCK:
        configs = read_ru_configs()
        if request.method == "GET":
            return jsonify(configs.get(ip, {"ru_count": 1, "cc_per_ru": 3}))
        payload = request.get_json(silent=True) or {}
        try:
            count = int(payload["ru_count"])
            cc = int(payload["cc_per_ru"])
        except (KeyError, ValueError, TypeError):
            return jsonify({"error": "Invalid RU configuration"}), 400
        if not 1 <= count <= 4 or not 1 <= cc <= 3:
            return jsonify({"error": "RU Count must be 1-4 and CC per RU 1-3"}), 400
        config = {"ru_count": count, "cc_per_ru": cc}
        configs[ip] = config
        try:
            RU_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = RU_CONFIG_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(configs, indent=2), encoding="utf-8")
            tmp.replace(RU_CONFIG_FILE)
        except OSError as exc:
            return jsonify({"error": str(exc)}), 500
        return jsonify(config)

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

    if GNB_DEVICE_TYPES.get(ip) == "PS2400":
        return jsonify({"cells": [{"cc": 0, "cell_id": 0,
            "dl": db.get_throughput_history(gnb_ip=ip, duration=duration, cell_id=0, column="dl_throughput"),
            "ul": db.get_throughput_history(gnb_ip=ip, duration=duration, cell_id=0, column="ul_throughput")}]})

    with RU_CONFIG_LOCK:
        config = read_ru_configs().get(ip, {"ru_count": 1, "cc_per_ru": 3})
    try:
        ru = int(request.args.get("ru", "1"))
    except ValueError:
        return jsonify({"error": "Invalid RU"}), 400
    if not 1 <= ru <= config["ru_count"]:
        return jsonify({"error": "RU outside configured range"}), 400
    base_cell = (ru - 1) * config["cc_per_ru"]
    cells = []
    for cc in range(config["cc_per_ru"]):
        cell_id = base_cell + cc
        cells.append({
            "cc": cc,
            "cell_id": cell_id,
            "dl": db.get_throughput_history(gnb_ip=ip, duration=duration, cell_id=cell_id, column="dl_throughput"),
            "ul": db.get_throughput_history(gnb_ip=ip, duration=duration, cell_id=cell_id, column="ul_throughput") if cell_id <= 2 else []
        })
    return jsonify({"cells": cells})


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
            gnb.get_oru_controller_boot_log_logs()

    })


# =========================================================
# RU logs: safe selection by RU number and known log type
# =========================================================

@app.route("/api/ru-log")
def ru_log():
    ip = request.args.get("ip", "")
    ru = request.args.get("ru", "1")
    log_type = request.args.get("type", "dsp_console")
    valid_types = {"dsp_console", "rumanager"}

    if ip not in GNB_POOL:
        return jsonify({"error": "Unknown gNB IP"}), 400
    if ru not in {"1", "2", "3", "4"} or log_type not in valid_types:
        return jsonify({"error": "Invalid RU or log type"}), 400

    gnb = get_gnb(ip)
    if gnb is None or gnb.ssh_client is None:
        return jsonify({"error": f"gNB {ip} is not connected"}), 503

    # LOGS_BACKUP: use the RU-specific prefix and allow timestamp/suffix variants.
    # The DSP filename can be ru1_DSP... or ru1_dsp_console...
    # (case-insensitive matching is handled by find -iname).
    patterns = ([f"ru{ru}_rumanager*"] if log_type == "rumanager"
                else [f"ru{ru}_DSP*", f"ru{ru}_dsp_console*"])
    import shlex
    find_names = " -o ".join(f"-iname {shlex.quote(pattern)}" for pattern in patterns)
    command = (
        'file=$(find /workspace/LOGS_BACKUP -maxdepth 1 -type f '
        f'\\( {find_names} \\) -printf "%T@ %p\\n" 2>/dev/null '
        '| sort -nr | head -n 1 | cut -d" " -f2-); '
        'if [ -n "$file" ] && [ -f "$file" ]; then '
        'printf "[File] %s\\n" "$file"; '
        'tail -n 200 -- "$file"; '
        'else printf "[RU log] No matching file found\\n"; fi'
    )
    try:
        transport = gnb.ssh_client.get_transport()
        if transport is None or not transport.is_active():
            return jsonify({"error": f"gNB {ip} SSH is disconnected"}), 503
        _, stdout, stderr = gnb.ssh_client.exec_command(command, timeout=8)
        stdout.channel.settimeout(8)
        content = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return jsonify({"ip": ip, "ru": int(ru), "type": log_type,
                        "content": content or err or "(Log is empty)"})
    except Exception as exc:
        app.logger.warning("[RU Log][%s] %s", ip, exc)
        return jsonify({"error": f"Failed to read RU log from {ip}"}), 502


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    # =====================================================
    # No gNB monitors are started at application launch.
    # =====================================================

    # Device monitors are started only by POST /api/gnbs.

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

        port=5000

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
