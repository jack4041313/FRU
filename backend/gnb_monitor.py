import threading

from backend.ognb_component.ognb_server import ognb

# =========================================================
# Current gNB instance
# =========================================================

_current_gnb = None


# =========================================================
# Get current gNB
# =========================================================

def get_gnb():
    return _current_gnb


# =========================================================
# Start gNB monitor
# =========================================================

def start_gnb_monitor(
        ip_address,
        username,
        password,
        port=22
):
    global _current_gnb

    print(
        f"[gNB Monitor] "
        f"Starting gNB monitor: {ip_address}"
    )

    # =====================================================
    # Create gNB object
    # =====================================================

    _current_gnb = ognb(

        ip_address=ip_address,

        username=username,

        password=password,

        port=port

    )

    _current_gnb.connect()

    print(
        f"[gNB Monitor] "
        f"gNB object created: {ip_address}"
    )

    # =====================================================
    # Start throughput monitor
    #
    # scan_throughput() 裡面會自動啟動
    # Netconf monitor
    # =====================================================

    try:

        _current_gnb.scan_throughput()

    except Exception as e:

        print(
            f"[gNB Monitor] "
            f"Monitor stopped: {e}\n"
        )


# =========================================================
# Start gNB monitor in background thread
# =========================================================

def start_gnb_monitor_thread(
        ip_address,
        username,
        password,
        port=22
):
    monitor_thread = threading.Thread(

        target=start_gnb_monitor,

        args=(

            ip_address,

            username,

            password,

            port

        ),

        daemon=True

    )

    monitor_thread.start()

    print(
        f"[gNB Monitor] "
        f"Monitor thread started: {ip_address}\n"
    )

    return monitor_thread
