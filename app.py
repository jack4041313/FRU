import time
import threading

from backend.database import GNBDatabase
from backend.gnb_monitor import start_gnb_monitor, get_gnb, start_gnb_monitor_thread
from flask import Flask, render_template, jsonify, request


app = Flask(__name__)

db = GNBDatabase()


@app.route("/")
def index():
    return render_template(
        "dashboard.html"
    )


@app.route("/api/throughput")
def throughput():
    duration = request.args.get(
        "range",
        "10m"
    )

    return jsonify({

        "cell0_dl": db.get_throughput_history(
            duration=duration,
            cell_id=0,
            column="dl_throughput"
        ),

        "cell0_ul": db.get_throughput_history(
            duration=duration,
            cell_id=0,
            column="ul_throughput"
        ),

        "cell1_dl": db.get_throughput_history(
            duration=duration,
            cell_id=1,
            column="dl_throughput"
        ),

        "cell1_ul": db.get_throughput_history(
            duration=duration,
            cell_id=1,
            column="ul_throughput"
        )

    })


def cleanup():
    while True:
        db.delete_old_data()

        time.sleep(
            86400
        )


@app.route("/api/logs")
def logs():

    gnb = get_gnb()

    if gnb is None:

        return jsonify({
            "netconf": []
        })

    return jsonify({

        "netconf":
            gnb.get_netconf_logs(),

        "rumanager":
            gnb.get_rumanager_logs()

    })


if __name__ == "__main__":

    # ==========================================
    # Start gNB monitor
    # ==========================================

    start_gnb_monitor_thread(
        ip_address="10.255.174.7",
        username="ognb",
        password="ognb123",
        port=22
    )

    # ==========================================
    # Start database cleanup
    # ==========================================

    threading.Thread(
        target=cleanup,
        daemon=True
    ).start()

    # ==========================================
    # Start Flask
    # ==========================================

    app.run(
        host="0.0.0.0",
        port=5000
    )