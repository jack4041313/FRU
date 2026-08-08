import time
import threading

from backend.database import GNBDatabase
from backend.gnb_monitor import start_gnb_monitor
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
    return jsonify({

        "log1":
            "Waiting for gNB log...",

        "log2":
            "Waiting for RU log..."

    })


if __name__ == "__main__":
    threading.Thread(
        target=start_gnb_monitor,
        daemon=True
    ).start()

    threading.Thread(
        target=cleanup,
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=5000
    )
