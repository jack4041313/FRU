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
import traceback


def start_throughput_monitor(gnb):

    print(
        f"[Throughput] Monitor start: "
        f"{gnb.ip_address}"
    )

    try:

        gnb.scan_throughput()

        print(
            "[Throughput] "
            "scan_throughput() returned normally"
        )

    except Exception as e:

        print(
            "[Throughput] "
            f"Monitor stopped: {repr(e)}"
        )

        traceback.print_exc()


# =========================================================
# Netconf Monitor
# =========================================================

def start_netconf_monitor(gnb):

    """
    Start Netconf server log monitor.

    The actual monitoring is handled by
    start_netconf_monitor() inside ognb.
    """

    try:

        print(
            f"[Netconf] "
            f"Monitor start: {gnb.ip_address}"
        )

        gnb.start_netconf_monitor()

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
    Start RU Manager log monitor.

    The actual monitoring is handled by
    start_rumanager_monitor() inside ognb.
    """

    try:

        print(
            f"[RU Manager] "
            f"Monitor start: {gnb.ip_address}"
        )

        gnb.start_rumanager_monitor()

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

    print(
        f"[gNB Monitor] "
        f"Starting gNB monitor: {ip_address}"
    )

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

        print(
            f"[gNB Monitor] "
            f"gNB object created: {ip_address}"
        )

    except Exception as e:

        print(
            f"[gNB Monitor] "
            f"Failed to create gNB object: {e}"
        )

        _current_gnb = None

        return

    # =====================================================
    # Connect
    # =====================================================

    try:

        _current_gnb.connect()

        print(
            f"[gNB Monitor] "
            f"gNB connected: {ip_address}"
        )

    except Exception as e:

        print(
            f"[gNB Monitor] "
            f"Failed to connect to gNB: {e}"
        )

        _current_gnb = None

        return

    # =====================================================
    # Start all monitors
    # =====================================================

    print(
        f"[gNB Monitor] "
        f"Starting all monitors: {ip_address}"
    )

    # =====================================================
    # Throughput
    # =====================================================

    throughput_thread = threading.Thread(

        target=start_throughput_monitor,

        args=(
            _current_gnb,
        ),

        daemon=True,

        name="ThroughputMonitor"

    )

    throughput_thread.start()

    # =====================================================
    # Netconf
    # =====================================================

    netconf_thread = threading.Thread(

        target=start_netconf_monitor,

        args=(
            _current_gnb,
        ),

        daemon=True,

        name="NetconfMonitor"

    )

    netconf_thread.start()

    # =====================================================
    # RU Manager
    # =====================================================

    rumanager_thread = threading.Thread(

        target=start_rumanager_monitor,

        args=(
            _current_gnb,
        ),

        daemon=True,

        name="RUManagerMonitor"

    )

    rumanager_thread.start()

    # =====================================================
    # Status
    # =====================================================

    # print(
    #     f"[gNB Monitor] "
    #     f"All monitor threads started: {ip_address}"
    # )
    #
    # print(
    #     f"[gNB Monitor] "
    #     f"Throughput thread alive: "
    #     f"{throughput_thread.is_alive()}"
    # )
    #
    # print(
    #     f"[gNB Monitor] "
    #     f"Netconf thread alive: "
    #     f"{netconf_thread.is_alive()}"
    # )
    #
    # print(
    #     f"[gNB Monitor] "
    #     f"RU Manager thread alive: "
    #     f"{rumanager_thread.is_alive()}"
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

        daemon=True,

        name="GNBMonitor"

    )

    monitor_thread.start()

    print(
        f"[gNB Monitor] "
        f"Monitor thread started: {ip_address}"
    )

    return monitor_thread
