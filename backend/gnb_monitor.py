import threading
import traceback

from backend.ognb_component.ognb_server import ognb

# =========================================================
# gNB Pool
#
# {
#     "10.255.174.7":  gNB object,
#     "10.255.174.239": gNB object,
#     ...
# }
# =========================================================

_gnb_pool = {}

# =========================================================
# Lock
#
# Prevent multiple users from creating the same gNB
# monitor at the same time.
# =========================================================

_gnb_pool_lock = threading.Lock()


# =========================================================
# Get gNB
# =========================================================

def get_gnb(ip_address):
    return _gnb_pool.get(
        ip_address
    )


# =========================================================
# Get all gNBs
# =========================================================

def get_gnb_pool():
    return _gnb_pool


# =========================================================
# Throughput Monitor
# =========================================================

def start_throughput_monitor(gnb):
    print(
        f"[Throughput] Monitor start: "
        f"{gnb.ip_address}"
    )

    try:

        gnb.scan_throughput()

        print(
            f"[Throughput] "
            f"scan_throughput() returned normally: "
            f"{gnb.ip_address}"
        )

    except Exception as e:

        print(
            f"[Throughput] "
            f"Monitor stopped: "
            f"{gnb.ip_address} "
            f"{repr(e)}"
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
            f"Monitor start: "
            f"{gnb.ip_address}"
        )

        gnb.start_netconf_monitor()

    except Exception as e:

        print(
            f"[Netconf] "
            f"Monitor stopped: "
            f"{gnb.ip_address} "
            f"{e}"
        )

        traceback.print_exc()


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
            f"Monitor start: "
            f"{gnb.ip_address}"
        )

        gnb.start_rumanager_monitor()

    except Exception as e:

        print(
            f"[RU Manager] "
            f"Monitor stopped: "
            f"{gnb.ip_address} "
            f"{e}"
        )

        traceback.print_exc()


# =========================================================
# Start gNB monitor
# =========================================================

def start_gnb_monitor(
        ip_address,
        username,
        password,
        port=22
):
    print(
        f"[gNB Monitor] "
        f"Starting gNB monitor: "
        f"{ip_address}"
    )

    # =====================================================
    # Check whether monitor already exists
    # =====================================================

    with _gnb_pool_lock:

        if ip_address in _gnb_pool:
            print(
                f"[gNB Monitor] "
                f"Monitor already exists: "
                f"{ip_address}"
            )

            return _gnb_pool[
                ip_address
            ]

        # =================================================
        # Create gNB object
        # =================================================

        try:

            gnb = ognb(

                ip_address=ip_address,

                username=username,

                password=password,

                port=port

            )

            print(
                f"[gNB Monitor] "
                f"gNB object created: "
                f"{ip_address}"
            )

        except Exception as e:

            print(
                f"[gNB Monitor] "
                f"Failed to create gNB object: "
                f"{ip_address} "
                f"{e}"
            )

            traceback.print_exc()

            return None

        # =================================================
        # Put object into pool
        #
        # Put it here before starting monitor threads.
        # This prevents another request from creating
        # another object for the same IP.
        # =================================================

        _gnb_pool[
            ip_address
        ] = gnb

    # =====================================================
    # Connect
    # =====================================================

    try:

        gnb.connect()

        print(
            f"[gNB Monitor] "
            f"gNB connected: "
            f"{ip_address}"
        )

    except Exception as e:

        print(
            f"[gNB Monitor] "
            f"Failed to connect to gNB: "
            f"{ip_address} "
            f"{e}"
        )

        traceback.print_exc()

        # =================================================
        # Remove failed gNB from pool
        # =================================================

        with _gnb_pool_lock:

            if _gnb_pool.get(
                    ip_address
            ) is gnb:
                del _gnb_pool[
                    ip_address
                ]

        return None

    # =====================================================
    # Start all monitors
    # =====================================================

    print(
        f"[gNB Monitor] "
        f"Starting all monitors: "
        f"{ip_address}"
    )

    # =====================================================
    # Throughput
    # =====================================================

    throughput_thread = threading.Thread(

        target=start_throughput_monitor,

        args=(
            gnb,
        ),

        daemon=True,

        name=f"ThroughputMonitor-{ip_address}"

    )

    throughput_thread.start()

    # =====================================================
    # Netconf
    # =====================================================

    netconf_thread = threading.Thread(

        target=start_netconf_monitor,

        args=(
            gnb,
        ),

        daemon=True,

        name=f"NetconfMonitor-{ip_address}"

    )

    netconf_thread.start()

    # =====================================================
    # RU Manager
    # =====================================================

    rumanager_thread = threading.Thread(

        target=start_rumanager_monitor,

        args=(
            gnb,
        ),

        daemon=True,

        name=f"RUManagerMonitor-{ip_address}"

    )

    rumanager_thread.start()

    # =====================================================
    # Status
    # =====================================================

    print(
        f"[gNB Monitor] "
        f"All monitor threads started: "
        f"{ip_address}"
    )

    print(
        f"[gNB Monitor] "
        f"Throughput thread alive: "
        f"{throughput_thread.is_alive()}"
    )

    print(
        f"[gNB Monitor] "
        f"Netconf thread alive: "
        f"{netconf_thread.is_alive()}"
    )

    print(
        f"[gNB Monitor] "
        f"RU Manager thread alive: "
        f"{rumanager_thread.is_alive()}"
    )

    return gnb


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

        name=f"GNBMonitor-{ip_address}"

    )

    monitor_thread.start()

    print(
        f"[gNB Monitor] "
        f"Monitor thread started: "
        f"{ip_address}"
    )

    return monitor_thread
