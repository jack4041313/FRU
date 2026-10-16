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
_gnb_starting = set()
_gnb_stopping = set()
_gnb_threads = {}


def is_gnb_starting(ip_address):
    with _gnb_pool_lock:
        return ip_address in _gnb_starting


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

def start_bootlog_monitor(gnb):
    """
    Start RU Manager log monitor.

    The actual monitoring is handled by
    start_bootlog_monitor() inside ognb.
    """

    try:

        print(
            f"[RU Manager] "
            f"Monitor start: "
            f"{gnb.ip_address}"
        )

        gnb.start_bootlog_monitor()

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

        target=start_bootlog_monitor,

        args=(
            gnb,
        ),

        daemon=True,

        name=f"RUManagerMonitor-{ip_address}"

    )

    rumanager_thread.start()

    with _gnb_pool_lock:
        _gnb_threads[ip_address] = [throughput_thread, netconf_thread, rumanager_thread]

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

def _run_reserved_monitor(ip_address, username, password, port):
    try:
        start_gnb_monitor(ip_address, username, password, port)
    finally:
        with _gnb_pool_lock:
            _gnb_starting.discard(ip_address)


def start_gnb_monitor_thread(
        ip_address,
        username,
        password,
        port=22
):
    with _gnb_pool_lock:
        if ip_address in _gnb_pool or ip_address in _gnb_starting or ip_address in _gnb_stopping:
            print(f"[gNB Monitor] Already running or connecting: {ip_address}")
            return None
        _gnb_starting.add(ip_address)

    monitor_thread = threading.Thread(

        target=_run_reserved_monitor,

        args=(

            ip_address,

            username,

            password,

            port

        ),

        daemon=True,

        name=f"GNBMonitor-{ip_address}"

    )

    try:
        monitor_thread.start()
    except Exception:
        with _gnb_pool_lock:
            _gnb_starting.discard(ip_address)
        raise

    print(
        f"[gNB Monitor] "
        f"Monitor thread started: "
        f"{ip_address}"
    )

    return monitor_thread


def stop_gnb_monitor(ip_address, timeout=5):
    """Stop workers and SSH; remove from pool only after workers exit.

    Returns (success, message). A connecting gNB must finish connecting first.
    """
    with _gnb_pool_lock:
        if ip_address in _gnb_starting:
            return False, "gNB is still connecting; retry removal shortly"
        if ip_address in _gnb_stopping:
            return False, "gNB is already stopping"
        gnb = _gnb_pool.get(ip_address)
        if gnb is None:
            return True, "No active monitor"
        _gnb_stopping.add(ip_address)

    try:
        gnb.stop_all_monitors()
        threads = _gnb_threads.get(ip_address, [])
        # Internal scan threads are started by ognb itself.
        threads = threads + [getattr(gnb, name, None) for name in
                             ("netconf_thread", "rumanager_thread", "throughput_thread")]
        for thread in threads:
            if thread and thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=timeout)
        alive = [thread.name for thread in threads if thread and thread.is_alive()]
        if alive:
            return False, f"Monitor threads have not exited: {', '.join(alive)}"
        with _gnb_pool_lock:
            if _gnb_pool.get(ip_address) is gnb:
                del _gnb_pool[ip_address]
            _gnb_threads.pop(ip_address, None)
        try:
            gnb.db.conn.close()
        except Exception:
            pass
        return True, "Stopped"
    except Exception as exc:
        traceback.print_exc()
        return False, str(exc)
    finally:
        with _gnb_pool_lock:
            _gnb_stopping.discard(ip_address)
