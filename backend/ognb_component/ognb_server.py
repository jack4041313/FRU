import time
import threading

from collections import deque
from datetime import datetime

from backend.database import GNBDatabase
from backend.ognb_component.base_server import server


class ognb(server):

    def __init__(
            self,
            ip_address,
            username,
            password,
            port=22
    ):

        super().__init__(
            ip_address,
            username,
            password,
            port
        )

        # =========================================================
        # Database
        # =========================================================

        self.db = GNBDatabase()

        # =========================================================
        # Throughput
        # =========================================================

        self.throughput_monitor = None

        self.last_throughput_time = time.time()

        # =========================================================
        # Netconf
        # =========================================================

        self.netconf_session = None

        self.netconf_logs = deque(
            maxlen=200
        )

        self.netconf_running = False

        self.netconf_thread = None

        # =========================================================
        # RU Manager
        # =========================================================

        self.rumanager_session = None

        self.rumanager_logs = deque(
            maxlen=200
        )

        self.rumanager_running = False

        self.rumanager_thread = None

    def __del__(self):

        print("")

    # =========================================================
    # Super User
    # =========================================================

    def super_user(self):

        self.ssh_session.send(
            "su\n"
        )

        print(
            self.ssh_session
            .recv(2048)
            .decode(
                "utf-8",
                errors="ignore"
            )
            .split("\n")
        )

        self.ssh_session.send(
            "RAdisys@1234\n"
        )

        print(
            self.ssh_session
            .recv(2048)
            .decode(
                "utf-8",
                errors="ignore"
            )
            .split("\n")
        )

    # =========================================================
    # Netconf Log Monitor
    # =========================================================

    def start_netconf_monitor(self):

        if self.netconf_running:
            print(
                "[Netconf] "
                "Monitor already running"
            )

            return

        try:

            # -----------------------------------------------------
            # Create independent SSH channel
            # -----------------------------------------------------

            transport = (
                self.ssh_session
                .get_transport()
            )

            if transport is None:
                print(
                    "[Netconf] "
                    "Cannot get SSH transport"
                )

                return

            self.netconf_session = (
                transport.open_session()
            )

            self.netconf_session.get_pty()

            self.netconf_session.invoke_shell()

            time.sleep(1)

            # -----------------------------------------------------
            # Clear login message
            # -----------------------------------------------------

            while (
                    self.netconf_session
                            .recv_ready()
            ):
                self.netconf_session.recv(
                    4096
                )

            # -----------------------------------------------------
            # Find netconf trace log
            # -----------------------------------------------------

            self.netconf_session.send(
                "ls /workspace/logs/"
                "*oru_cntrl_netconf_trace*.log\n"
            )

            time.sleep(2)

            data = ""

            while (
                    self.netconf_session
                            .recv_ready()
            ):
                data += (

                    self.netconf_session
                    .recv(4096)
                    .decode(
                        errors="ignore"
                    )

                )

            log_file = None

            for line in data.splitlines():

                line = line.strip()

                if (
                        "oru_cntrl_netconf_trace"
                        in line
                        and
                        line.endswith(".log")
                ):
                    log_file = line

                    break

            # -----------------------------------------------------
            # Log not found
            # -----------------------------------------------------

            if log_file is None:
                self.add_netconf_log(
                    "ERROR: Cannot find "
                    "oru_cntrl_netconf_trace*.log"
                )

                print(
                    "[Netconf] "
                    "Cannot find trace log"
                )

                return

            self.add_netconf_log(
                f"Monitoring: {log_file}"
            )

            print(
                f"[Netconf] "
                f"Monitoring {log_file}"
            )

            # -----------------------------------------------------
            # Start tail
            # -----------------------------------------------------

            self.netconf_session.send(
                f"tail -F {log_file}\n"
            )

            self.netconf_running = True

            # -----------------------------------------------------
            # Start thread
            # -----------------------------------------------------

            self.netconf_thread = (
                threading.Thread(

                    target=self.scan_netconf_log,

                    daemon=True

                )
            )

            self.netconf_thread.start()


        except Exception as e:

            print(
                f"[Netconf] "
                f"Monitor start failed: {e}"
            )

            self.add_netconf_log(
                f"ERROR: {e}"
            )

    # =========================================================
    # Scan Netconf Log
    # =========================================================

    def scan_netconf_log(self):

        buffer = ""

        while self.netconf_running:

            try:

                if (
                        self.netconf_session
                        is None
                ):
                    break

                while (
                        self.netconf_session
                                .recv_ready()
                ):

                    data = (

                        self.netconf_session
                        .recv(4096)
                        .decode(
                            errors="ignore"
                        )

                    )

                    if not data:
                        break

                    buffer += data

                    lines = buffer.split(
                        "\n"
                    )

                    buffer = lines[-1]

                    for line in lines[:-1]:

                        line = line.rstrip()

                        if not line:
                            continue

                        timestamp = (
                            datetime.now()
                            .strftime(
                                "%Y-%m-%d "
                                "%H:%M:%S"
                            )
                        )

                        log_line = (
                            f"[{timestamp}] "
                            f"{line}"
                        )

                        self.add_netconf_log(
                            log_line
                        )

                time.sleep(0.2)

            except Exception as e:

                self.add_netconf_log(
                    f"ERROR: {e}"
                )

                break

        print(
            "[Netconf] "
            "Monitor stopped"
        )

    # =========================================================
    # Add Netconf Log
    # =========================================================

    def add_netconf_log(
            self,
            line
    ):

        self.netconf_logs.append(
            line
        )

    # =========================================================
    # Get Netconf Logs
    # =========================================================

    def get_netconf_logs(self):

        return "\n".join(
            self.netconf_logs
        )

    # =========================================================
    # Stop Netconf Monitor
    # =========================================================

    def stop_netconf_monitor(self):

        self.netconf_running = False

        if self.netconf_session:

            try:

                self.netconf_session.close()

            except Exception:

                pass

            self.netconf_session = None

    # =========================================================
    # RU Manager Monitor
    # =========================================================

    def start_rumanager_monitor(
            self,
            log_path="/workspace/logs/RU1_rumanager"
    ):

        if self.rumanager_running:
            print(
                "[RU Manager] "
                "Monitor already running"
            )

            return

        try:

            # -----------------------------------------------------
            # Create independent SSH channel
            # -----------------------------------------------------

            transport = (
                self.ssh_session
                .get_transport()
            )

            if transport is None:
                print(
                    "[RU Manager] "
                    "Cannot get SSH transport"
                )

                return

            self.rumanager_session = (
                transport.open_session()
            )

            self.rumanager_session.get_pty()

            self.rumanager_session.invoke_shell()

            time.sleep(1)

            # -----------------------------------------------------
            # Clear login message
            # -----------------------------------------------------

            while (
                    self.rumanager_session
                            .recv_ready()
            ):
                self.rumanager_session.recv(
                    4096
                )

            # -----------------------------------------------------
            # Start tail
            # -----------------------------------------------------

            self.rumanager_session.send(
                f"tail -F {log_path}\n"
            )

            self.rumanager_running = True

            print(
                "[RU Manager] "
                f"Monitoring {log_path}"
            )

            # -----------------------------------------------------
            # Start thread
            # -----------------------------------------------------

            self.rumanager_thread = (
                threading.Thread(

                    target=self.scan_rumanager_log,

                    daemon=True

                )
            )

            self.rumanager_thread.start()


        except Exception as e:

            print(
                f"[RU Manager] "
                f"Monitor start failed: {e}"
            )

            self.add_rumanager_log(
                f"ERROR: {e}"
            )

    # =========================================================
    # Scan RU Manager Log
    # =========================================================

    def scan_rumanager_log(self):

        buffer = ""

        while self.rumanager_running:

            try:

                if (
                        self.rumanager_session
                        is None
                ):
                    break

                while (
                        self.rumanager_session
                                .recv_ready()
                ):

                    data = (

                        self.rumanager_session
                        .recv(4096)
                        .decode(
                            errors="ignore"
                        )

                    )

                    if not data:
                        break

                    buffer += data

                    lines = buffer.split(
                        "\n"
                    )

                    buffer = lines[-1]

                    for line in lines[:-1]:

                        line = line.rstrip()

                        if not line:
                            continue

                        timestamp = (
                            datetime.now()
                            .strftime(
                                "%Y-%m-%d "
                                "%H:%M:%S"
                            )
                        )

                        log_line = (
                            f"[{timestamp}] "
                            f"{line}"
                        )

                        # -----------------------------------------
                        # Console
                        # -----------------------------------------

                        # print(
                        #     f"[RU Manager] "
                        #     f"{log_line}"
                        # )

                        # -----------------------------------------
                        # Memory only
                        #
                        # 不寫 SQLite
                        # -----------------------------------------

                        self.add_rumanager_log(
                            log_line
                        )

                time.sleep(0.2)


            except Exception as e:

                self.add_rumanager_log(
                    f"ERROR: {e}"
                )

                break

        print(
            "[RU Manager] "
            "Monitor stopped"
        )

    # =========================================================
    # Add RU Manager Log
    # =========================================================

    def add_rumanager_log(
            self,
            line
    ):

        self.rumanager_logs.append(
            line
        )

    # =========================================================
    # Get RU Manager Logs
    # =========================================================

    def get_rumanager_logs(self):

        return "\n".join(
            self.rumanager_logs
        )

    # =========================================================
    # Stop RU Manager Monitor
    # =========================================================

    def stop_rumanager_monitor(self):

        self.rumanager_running = False

        if self.rumanager_session:

            try:

                self.rumanager_session.close()

            except Exception:

                pass

            self.rumanager_session = None

    # =========================================================
    # Throughput Monitor
    # =========================================================

    def scan_throughput(
            self,
            log_path="/workspace/logs/l1_log_tdd"
    ):

        print(
            "[Throughput] "
            f"Monitoring {log_path}"
        )

        # ---------------------------------------------------------
        # Start Netconf
        # ---------------------------------------------------------

        self.start_netconf_monitor()

        # ---------------------------------------------------------
        # Start RU Manager
        # ---------------------------------------------------------

        self.start_rumanager_monitor()

        # ---------------------------------------------------------
        # Throughput uses main SSH session
        # ---------------------------------------------------------

        self.ssh_session.send(
            f"tail -F {log_path}\n"
        )

        buffer = ""

        while True:

            # =====================================================
            # Throughput timeout
            # =====================================================

            if (
                    time.time()
                    -
                    self.last_throughput_time
                    >
                    30
            ):
                timestamp = (
                    datetime.now()
                    .strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )

                print(
                    f"[{timestamp}] "
                    "No throughput data, "
                    "gNB may crash"
                )

                # -------------------------------------------------
                # Cell 0
                # -------------------------------------------------

                self.db.insert_throughput(

                    gnb_ip=self.ip_address,

                    cell_id=0,

                    dl_throughput=0,

                    ul_throughput=0,

                    ul_bler=0

                )

                # -------------------------------------------------
                # Cell 1
                # -------------------------------------------------

                self.db.insert_throughput(

                    gnb_ip=self.ip_address,

                    cell_id=1,

                    dl_throughput=0,

                    ul_throughput=0,

                    ul_bler=0

                )

                self.last_throughput_time = (
                    time.time()
                )

            # =====================================================
            # Receive throughput data
            # =====================================================

            while self.ssh_session.recv_ready():

                try:

                    data = (

                        self.ssh_session
                        .recv(4096)
                        .decode(
                            errors="ignore"
                        )

                    )

                except Exception as e:

                    print(
                        "[Throughput] "
                        f"SSH recv error: {e}"
                    )

                    break

                if not data:
                    break

                buffer += data

                lines = buffer.split(
                    "\n"
                )

                buffer = lines[-1]

                for line in lines[:-1]:

                    # -------------------------------------------------
                    # Cell detection
                    # -------------------------------------------------

                    if "0 (MU " in line:

                        cell_id = 0

                    elif "1 (MU " in line:

                        cell_id = 1

                    else:

                        continue

                    try:

                        parts = line.split("|")

                        if len(parts) <= 4:
                            continue

                        # =================================================
                        # DL
                        # =================================================

                        dl_field = (
                            parts[3]
                            .strip()
                        )

                        dl_values = (
                            dl_field.split()
                        )

                        if not dl_values:
                            continue

                        dl_throughput = (

                                float(
                                    dl_values[0]
                                    .replace(
                                        ",",
                                        ""
                                    )
                                )
                                / 1000

                        )

                        # =================================================
                        # UL
                        # =================================================

                        ul_field = (
                            parts[4]
                            .strip()
                        )

                        ul_values = (
                            ul_field.split()
                        )

                        if len(ul_values) < 4:
                            continue

                        ul_throughput = (

                                float(
                                    ul_values[0]
                                    .replace(
                                        ",",
                                        ""
                                    )
                                )
                                / 1000

                        )

                        # =================================================
                        # UL BLER
                        # =================================================

                        ul_bler = float(

                            ul_values[3]
                            .replace(
                                "%",
                                ""
                            )

                        )

                        # =================================================
                        # Update timestamp
                        # =================================================

                        self.last_throughput_time = (
                            time.time()
                        )

                        # =================================================
                        # Database
                        # =================================================

                        self.db.insert_throughput(

                            gnb_ip=self.ip_address,

                            cell_id=cell_id,

                            dl_throughput=(
                                dl_throughput
                            ),

                            ul_throughput=(
                                ul_throughput
                            ),

                            ul_bler=(
                                ul_bler
                            )

                        )

                        # =================================================
                        # Debug
                        # =================================================

                        timestamp = (
                            datetime.now()
                            .strftime(
                                "%Y-%m-%d "
                                "%H:%M:%S"
                            )
                        )

                        # print(
                        #
                        #     f"[{timestamp}] "
                        #
                        #     f"Cell-{cell_id} "
                        #
                        #     f"DL="
                        #     f"{dl_throughput:.3f} "
                        #     f"Mbps "
                        #
                        #     f"UL="
                        #     f"{ul_throughput:.3f} "
                        #     f"Mbps "
                        #
                        #     f"BLER="
                        #     f"{ul_bler:.2f}%"
                        #
                        # )


                    except (
                            IndexError,
                            ValueError,
                            TypeError
                    ):

                        continue

            # =====================================================
            # CPU protection
            # =====================================================

            time.sleep(1)
