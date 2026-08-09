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
# Throughput Monitor
# =========================================================

def start_throughput_monitor(gnb):
    """
    Monitor DL / UL throughput.

    scan_throughput() is a blocking function,
    therefore it runs in its own thread.
    """

    try:

        # print(
        #     f"[Throughput] "
        #     f"Monitor start: {gnb.ip_address}"
        # )

        gnb.scan_throughput()

    except Exception as e:

        print(
            f"[Throughput] "
            f"Monitor stopped: {e}"
        )


# =========================================================
# Netconf Monitor
# =========================================================

def start_netconf_monitor(gnb):
    """
    Monitor Netconf server log.

    The log is kept in memory only.
    It is NOT stored in SQLite.
    """

    try:

        # print(
        #     f"[Netconf] "
        #     f"Monitor start: {gnb.ip_address}"
        # )

        gnb.get_netconf_logs()

    except Exception as e:

        print(
            f"[Netconf] "
            f"Monitor stopped: {e}"
        )


# =========================================================
# RU Manager Monitor
# =========================================================

def start_rumanager_monitor(gnb):
    """
    Monitor RU Manager log.

    Log path:

        /workspace/logs/RU1_rumanager

    The log is kept in memory only.
    It is NOT stored in SQLite.
    """

    try:

        # print(
        #     f"[RU Manager] "
        #     f"Monitor start: {gnb.ip_address}"
        # )

        gnb.get_rumanager_logs()

    except Exception as e:

        print(
            f"[RU Manager] "
            f"Monitor stopped: {e}"
        )


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

    # print(
    #     f"[gNB Monitor] "
    #     f"Starting gNB monitor: {ip_address}"
    # )

    # =====================================================
    # Create gNB object
    # =====================================================

    try:

        _current_gnb = ognb(

            ip_address=ip_address,

            username=username,

            password=password,

            port=port

        )

        # print(
        #     f"[gNB Monitor] "
        #     f"gNB object created: {ip_address}"
        # )

    except Exception as e:

        print(
            f"[gNB Monitor] "
            f"Failed to create gNB object: {e}"
        )

        _current_gnb = None

        return

    # =====================================================
    # Connect to gNB
    # =====================================================

    try:

        _current_gnb.connect()

        # print(
        #     f"[gNB Monitor] "
        #     f"gNB connected: {ip_address}"
        # )

    except Exception as e:

        print(
            f"[gNB Monitor] "
            f"Failed to connect to gNB: {e}"
        )

        _current_gnb = None

        return

    # =====================================================
    # Start Throughput Monitor
    # =====================================================

    throughput_thread = threading.Thread(

        target=start_throughput_monitor,

        args=(
            _current_gnb,
        ),

        daemon=True

    )

    throughput_thread.start()

    # print(
    #     f"[gNB Monitor] "
    #     f"Throughput monitor started"
    # )

    # =====================================================
    # Start Netconf Monitor
    # =====================================================

    netconf_thread = threading.Thread(

        target=start_netconf_monitor,

        args=(
            _current_gnb,
        ),

        daemon=True

    )

    netconf_thread.start()

    print(
        f"[gNB Monitor] "
        f"Netconf monitor started"
    )

    # =====================================================
    # Start RU Manager Monitor
    # =====================================================

    rumanager_thread = threading.Thread(

        target=start_rumanager_monitor,

        args=(
            _current_gnb,
        ),

        daemon=True

    )

    rumanager_thread.start()

    # print(
    #     f"[gNB Monitor] "
    #     f"RU Manager monitor started"
    # )

    # =====================================================
    # Monitor status
    # =====================================================

    # print(
    #     f"[gNB Monitor] "
    #     f"All monitors started: {ip_address}"
    # )


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
        f"Monitor thread started: {ip_address}"
    )

    return monitor_thread

