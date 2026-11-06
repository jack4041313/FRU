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
    ips = list(DEFAULT_GNBS)
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

    if not existing or get_gnb(ip) is None:
        start_gnb_once(ip, config)
    return jsonify({"ip": ip, "added": not existing, "status": "connecting"}), (201 if not existing else 200)



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
            password=config["password"], port=config["port"]
        )
        GNB_MONITOR_THREADS[ip] = thread
        return thread

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
        try:
            save_gnb_ips()
        except OSError as exc:
            GNB_POOL[ip] = config
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
            "connected": False
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
        "connected": connected
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

    return jsonify({

        "cell0_dl": db.get_throughput_history(
            gnb_ip=ip,
            duration=duration,
            cell_id=0,
            column="dl_throughput"
        ),

        "cell0_ul": db.get_throughput_history(
            gnb_ip=ip,
            duration=duration,
            cell_id=0,
            column="ul_throughput"
        ),

        "cell1_dl": db.get_throughput_history(
            gnb_ip=ip,
            duration=duration,
            cell_id=1,
            column="dl_throughput"
        ),

        "cell1_ul": db.get_throughput_history(
            gnb_ip=ip,
            duration=duration,
            cell_id=1,
            column="ul_throughput"
        ),

        "cell2_dl": db.get_throughput_history(
            gnb_ip=ip,
            duration=duration,
            cell_id=2,
            column="dl_throughput"
        ),

        "cell2_ul": db.get_throughput_history(
            gnb_ip=ip,
            duration=duration,
            cell_id=2,
            column="ul_throughput"
        )

    })


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
    # Start all gNB monitors
    # =====================================================

    for ip, config in GNB_POOL.items():
        print(
            "[gNB Pool] "
            f"Starting monitor: {ip}"
        )

        start_gnb_once(ip, config)

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
