import time
import threading

from backend.database import GNBDatabase
from backend.gnb_monitor import (
    start_gnb_monitor_thread,
    get_gnb
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

GNB_POOL = {

    "10.255.174.7": {
        "username": "ognb",
        "password": "ognb123",
        "port": 22
    },

    # "10.255.174.239": {
    #     "username": "ognb",
    #     "password": "ognb123",
    #     "port": 22
    # },

    "10.255.175.105": {
        "username": "ognb",
        "password": "ognb123",
        "port": 22
    }

}


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
            gnb.get_rumanager_logs()

    })


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
