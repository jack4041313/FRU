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

        self.throughput_monitor = None

        self.db = GNBDatabase()

        self.last_throughput_time = time.time()

        # ==========================================
        # Netconf log
        # ==========================================

        self.netconf_session = None

        self.netconf_logs = deque(
            maxlen=200
        )

        self.netconf_running = False

        self.netconf_thread = None

    def __del__(self):

        print('')

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
            .decode('utf-8')
            .split('\n')
        )

        self.ssh_session.send(
            "RAdisys@1234\n"
        )

        print(
            self.ssh_session
            .recv(2048)
            .decode('utf-8')
            .split('\n')
        )

    # =========================================================
    # Netconf Log Monitor
    # =========================================================

    def start_netconf_monitor(self):

        if self.netconf_running:
            print(
                "Netconf monitor already running"
            )

            return

        try:

            # ------------------------------------------
            # 建立新的 SSH channel
            # ------------------------------------------

            transport = (
                self.ssh_session
                .get_transport()
            )

            if transport is None:
                print(
                    "Cannot get SSH transport"
                )

                return

            self.netconf_session = (
                transport.open_session()
            )

            self.netconf_session.get_pty()

            self.netconf_session.invoke_shell()

            time.sleep(1)

            # 清掉登入後可能存在的訊息

            if self.netconf_session.recv_ready():
                self.netconf_session.recv(
                    4096
                )

            # ------------------------------------------
            # 找 netconf trace log
            # ------------------------------------------

            self.netconf_session.send(
                "ls /workspace/logs/"
                "*oru_cntrl_netconf_trace*.log\n"
            )

            time.sleep(2)

            data = ""

            while (
                    self.netconf_session.recv_ready()
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
                        and line.endswith(".log")
                ):
                    log_file = line

                    break

            # ------------------------------------------
            # 找不到 log
            # ------------------------------------------

            if log_file is None:
                self.add_netconf_log(
                    "ERROR: Cannot find "
                    "oru_cntrl_netconf_trace*.log"
                )

                print(
                    "Cannot find netconf trace log"
                )

                return

            self.add_netconf_log(
                f"Monitoring: {log_file}"
            )

            print(
                f"[Netconf] "
                f"Monitoring {log_file}"
            )

            # ------------------------------------------
            # tail -F
            # ------------------------------------------

            self.netconf_session.send(
                f"tail -F {log_file}\n"
            )

            self.netconf_running = True

            # ------------------------------------------
            # Start thread
            # ------------------------------------------

            self.netconf_thread = threading.Thread(
                target=self.scan_netconf_log,
                daemon=True
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

                if (
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
    # Throughput Monitor
    # =========================================================

    def scan_throughput(
            self,
            log_path="/workspace/logs/l1_log_tdd"
    ):

        # ==========================================
        # 啟動 Netconf Monitor
        # ==========================================

        self.start_netconf_monitor()

        # ==========================================
        # Throughput
        # ==========================================

        self.ssh_session.send(
            f"tail -F {log_path}\n"
        )

        buffer = ""

        while True:

            # ==========================================
            # Check throughput timeout
            # ==========================================

            if (
                    time.time()
                    - self.last_throughput_time
                    > 30
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

                self.db.insert_throughput(

                    gnb_ip=self.ip_address,

                    cell_id=1,

                    dl_throughput=0,

                    ul_throughput=0,

                    ul_bler=0

                )

                # 避免一直寫0

                self.last_throughput_time = (
                    time.time()
                )

            # ==========================================
            # Receive SSH data
            # ==========================================

            if self.ssh_session.recv_ready():

                data = (
                    self.ssh_session
                    .recv(4096)
                    .decode(
                        errors="ignore"
                    )
                )

                buffer += data

                lines = buffer.split(
                    "\n"
                )

                buffer = lines[-1]

                for line in lines[:-1]:

                    # ----------------------------------
                    # Detect Cell
                    # ----------------------------------

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

                        # ==================================
                        # DL Throughput
                        # ==================================

                        dl_field = (
                            parts[3]
                            .strip()
                        )

                        dl_throughput = (

                                float(

                                    dl_field
                                    .split()[0]
                                    .replace(
                                        ",",
                                        ""
                                    )

                                )

                                / 1000

                        )

                        # ==================================
                        # UL Throughput + BLER
                        # ==================================

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

                        ul_bler = float(

                            ul_values[3]
                            .replace(
                                "%",
                                ""
                            )

                        )

                        # ==================================
                        # Update timestamp
                        # ==================================

                        self.last_throughput_time = (
                            time.time()
                        )

                        # ==================================
                        # Store DB
                        # ==================================

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

                        timestamp = (
                            datetime.now()
                            .strftime(
                                "%Y-%m-%d "
                                "%H:%M:%S"
                            )
                        )

                        # ==================================
                        # Debug
                        # ==================================

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
                            ValueError
                    ):

                        continue

            # ==========================================
            # CPU protection
            # ==========================================

            time.sleep(1)
