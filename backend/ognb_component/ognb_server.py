import time
import threading
import traceback

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
        # SSH Channels
        #
        # 1. throughput_session
        # 2. netconf_session
        # 3. rumanager_session
        #
        # 三個 monitor 各自使用獨立 channel
        # =========================================================

        self.throughput_session = None
        self.netconf_session = None
        self.rumanager_session = None

        # =========================================================
        # Throughput
        # =========================================================

        self.throughput_running = False
        self.throughput_thread = None
        self.uptime = "Unknown"

        self.last_throughput_time = time.time()

        # =========================================================
        # Netconf
        # =========================================================

        self.netconf_logs = deque(
            maxlen=200
        )

        self.netconf_running = False
        self.netconf_thread = None

        # =========================================================
        # RU Manager
        # =========================================================

        self.rumanager_logs = deque(
            maxlen=200
        )

        self.rumanager_running = False
        self.rumanager_thread = None

    def __del__(self):

        try:
            self.stop_all_monitors()
        except Exception:
            pass

    # =========================================================
    # Super User
    # =========================================================

    def super_user(self):

        if self.ssh_session is None:
            print(
                "[gNB] SSH session is not available"
            )
            return

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
    # Create SSH Channel
    #
    # 所有 monitor 共用同一個 SSH transport
    # 但各自建立獨立 channel
    # =========================================================

    def create_ssh_channel(self):

        if self.ssh_session is None:
            raise RuntimeError(
                "Main SSH session is not available"
            )

        transport = (
            self.ssh_session
            .get_transport()
        )

        if transport is None:
            raise RuntimeError(
                "SSH transport is not available"
            )

        if not transport.is_active():
            raise RuntimeError(
                "SSH transport is not active"
            )

        channel = transport.open_session()

        channel.get_pty()

        channel.invoke_shell()

        time.sleep(0.5)

        # ---------------------------------------------------------
        # 清除登入後可能存在的 banner / prompt
        # ---------------------------------------------------------

        while channel.recv_ready():

            try:

                channel.recv(
                    4096
                )

            except Exception:

                break

        return channel

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
            # 建立獨立 SSH channel
            # -----------------------------------------------------

            self.netconf_session = (
                self.create_ssh_channel()
            )

            if self.netconf_session is None:
                raise RuntimeError(
                    "Failed to create Netconf SSH channel"
                )

            # -----------------------------------------------------
            # 持續尋找 netconf trace log
            # -----------------------------------------------------

            while True:

                # -------------------------------------------------
                # 清除目前 channel buffer
                # -------------------------------------------------

                while self.netconf_session.recv_ready():
                    self.netconf_session.recv(
                        4096
                    )

                # -------------------------------------------------
                # 找 netconf trace log
                # -------------------------------------------------

                self.netconf_session.send(
                    "ls /workspace/logs/"
                    "*oru_cntrl_netconf_trace*.log\n"
                )

                time.sleep(1)

                data = ""

                while self.netconf_session.recv_ready():

                    chunk = (
                        self.netconf_session
                        .recv(4096)
                        .decode(
                            errors="ignore"
                        )
                    )

                    if not chunk:
                        break

                    data += chunk

                # -------------------------------------------------
                # 找 log file
                # -------------------------------------------------

                log_file = None

                for line in data.splitlines():

                    line = line.strip()

                    if (
                            line.startswith("/workspace/logs/")
                            and
                            "oru_cntrl_netconf_trace" in line
                            and
                            line.endswith(".log")
                    ):
                        log_file = line

                        break

                # -------------------------------------------------
                # 找不到 log
                # -------------------------------------------------

                if log_file is None:
                    print(
                        "[Netconf] "
                        "Cannot find trace log, "
                        "retrying..."
                    )

                    self.add_netconf_log(
                        "Waiting for Netconf trace log..."
                    )

                    time.sleep(2)

                    continue

                # -------------------------------------------------
                # 找到了 log
                # -------------------------------------------------

                print(
                    "[Netconf] "
                    f"Found trace log: {log_file}"
                )

                break

            # -----------------------------------------------------
            # 開始 tail
            # -----------------------------------------------------

            self.netconf_session.send(
                f"tail -F -- {log_file}\n"
            )

            # -----------------------------------------------------
            # Monitor state
            # -----------------------------------------------------

            self.netconf_running = True

            self.add_netconf_log(
                f"Monitoring: {log_file}"
            )

            print(
                "[Netconf] "
                f"Monitoring {log_file}"
            )

            # -----------------------------------------------------
            # Start thread
            # -----------------------------------------------------

            self.netconf_thread = threading.Thread(
                target=self.scan_netconf_log,
                daemon=True
            )

            self.netconf_thread.start()

        except Exception as e:

            print(
                "[Netconf] "
                f"Monitor start failed: {e}"
            )

            self.add_netconf_log(
                f"ERROR: {e}"
            )

            # -----------------------------------------------------
            # Cleanup
            # -----------------------------------------------------

            self.netconf_running = False

            if self.netconf_session:

                try:
                    self.netconf_session.close()

                except Exception:
                    pass

                self.netconf_session = None

            self.netconf_thread = None

    # =========================================================
    # Scan Netconf Log
    # =========================================================

    def scan_netconf_log(self):

        buffer = ""

        while self.netconf_running:

            try:

                if self.netconf_session is None:
                    break

                while self.netconf_session.recv_ready():

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

                    lines = buffer.split("\n")

                    buffer = lines[-1]

                    for line in lines[:-1]:

                        line = line.rstrip()

                        if not line:
                            continue

                        # -----------------------------------------
                        # 檢查 tail 是否因為 log file 消失而失敗
                        # -----------------------------------------

                        if (
                                "No such file or directory"
                                in line
                                or
                                "has become inaccessible"
                                in line
                        ):

                            print(
                                "[Netconf] "
                                "Log file disappeared, "
                                "searching for new log file..."
                            )

                            self.add_netconf_log(
                                "Netconf log file disappeared, "
                                "searching for new log file..."
                            )

                            # -------------------------------------
                            # 停止目前 monitor
                            # -------------------------------------

                            self.netconf_running = False

                            # -------------------------------------
                            # 關閉目前 SSH channel
                            # -------------------------------------

                            try:

                                self.netconf_session.close()

                            except Exception:
                                pass

                            self.netconf_session = None

                            # -------------------------------------
                            # 清除 buffer
                            # -------------------------------------

                            buffer = ""

                            # -------------------------------------
                            # 等待 gNB 建立新的 log file
                            # -------------------------------------

                            time.sleep(2)

                            # -------------------------------------
                            # 重新啟動 Netconf monitor
                            #
                            # start_netconf_monitor()
                            # 會持續搜尋直到找到新的 log
                            # -------------------------------------

                            self.start_netconf_monitor()

                            return

                        # -----------------------------------------
                        # 正常 log
                        # -----------------------------------------

                        timestamp = (
                            datetime.now()
                            .strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                        )

                        log_line = (
                            f"[{timestamp}] "
                            f"{line}"
                        )

                        # -----------------------------------------
                        # 儲存在 memory
                        # -----------------------------------------

                        self.add_netconf_log(
                            log_line
                        )

                time.sleep(0.2)

            except Exception as e:

                self.add_netconf_log(
                    f"ERROR: {e}"
                )

                print(
                    "[Netconf] "
                    f"Monitor error: {e}"
                )

                # -----------------------------------------
                # 停止目前 monitor
                # -----------------------------------------

                self.netconf_running = False

                # -----------------------------------------
                # 關閉目前 SSH channel
                # -----------------------------------------

                if self.netconf_session:

                    try:
                        self.netconf_session.close()

                    except Exception:
                        pass

                    self.netconf_session = None

                # -----------------------------------------
                # 清除 buffer
                # -----------------------------------------

                buffer = ""

                # -----------------------------------------
                # 等待後重新啟動
                #
                # start_netconf_monitor()
                # 會持續搜尋直到找到 log
                # -----------------------------------------

                time.sleep(2)

                self.start_netconf_monitor()

                return

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
            # 建立獨立 SSH channel
            # -----------------------------------------------------

            self.rumanager_session = (
                self.create_ssh_channel()
            )

            # -----------------------------------------------------
            # tail RU Manager log
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
                "[RU Manager] "
                f"Monitor start failed: {e}"
            )

            self.add_rumanager_log(
                f"ERROR: {e}"
            )

            if self.rumanager_session:

                try:
                    self.rumanager_session.close()
                except Exception:
                    pass

                self.rumanager_session = None

    # =========================================================
    # Scan RU Manager Log
    # =========================================================

    def scan_rumanager_log(self):

        buffer = ""

        while self.rumanager_running:

            try:

                if self.rumanager_session is None:
                    break

                while self.rumanager_session.recv_ready():

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
                                "%Y-%m-%d %H:%M:%S"
                            )
                        )

                        log_line = (
                            f"[{timestamp}] "
                            f"{line}"
                        )

                        # -----------------------------------------
                        # Memory only
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
    # Get Up-Time
    # =========================================================

    def get_uptime(self):

        return self.uptime

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
    #
    # 使用第三個獨立 SSH channel
    # =========================================================

    def start_throughput_monitor(
            self,
            log_path="/workspace/logs/l1_log_tdd"
    ):

        if self.throughput_running:
            print(
                "[Throughput] "
                "Monitor already running"
            )

            return

        try:

            # -----------------------------------------------------
            # 建立第三個獨立 SSH channel
            # -----------------------------------------------------

            self.throughput_session = (
                self.create_ssh_channel()
            )

            # -----------------------------------------------------
            # tail throughput log
            # -----------------------------------------------------

            self.throughput_session.send(
                f"tail -F {log_path}\n"
            )

            self.throughput_running = True

            print(
                "[Throughput] "
                f"Monitoring {log_path}"
            )

            # -----------------------------------------------------
            # Start thread
            # -----------------------------------------------------

            self.throughput_thread = (
                threading.Thread(
                    target=self.scan_throughput,
                    daemon=True
                )
            )

            self.throughput_thread.start()

        except Exception as e:

            print(
                "[Throughput] "
                f"Monitor start failed: {e}"
            )

            if self.throughput_session:

                try:
                    self.throughput_session.close()
                except Exception:
                    pass

                self.throughput_session = None

    # =========================================================
    # Scan Throughput
    # =========================================================

    def scan_throughput(
            self,
            log_path="/workspace/logs/l1_log_tdd"
    ):

        print(
            "[Throughput] "
            f"Monitoring {log_path}"
        )

        try:

            # ==========================================
            # Throughput SSH session
            # ==========================================

            if self.ssh_session is None:
                print(
                    "[Throughput] "
                    "SSH session is None"
                )

                return

            # ==========================================
            # Start tail
            # ==========================================

            command = (
                f"tail -F {log_path}\n"
            )

            print(
                "[Throughput] "
                f"Sending command: {command.strip()}"
            )

            self.ssh_session.send(
                command
            )

            print(
                "[Throughput] "
                "tail command sent"
            )

            buffer = ""

            # ==========================================
            # Monitor loop
            # ==========================================

            while True:

                # ======================================
                # Throughput timeout
                # ======================================

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

                    # ----------------------------------
                    # Cell 0
                    # ----------------------------------

                    self.db.insert_throughput(

                        gnb_ip=self.ip_address,

                        cell_id=0,

                        dl_throughput=0,

                        ul_throughput=0,

                        ul_bler=0

                    )

                    # ----------------------------------
                    # Cell 1
                    # ----------------------------------

                    self.db.insert_throughput(

                        gnb_ip=self.ip_address,

                        cell_id=1,

                        dl_throughput=0,

                        ul_throughput=0,

                        ul_bler=0

                    )

                    # ----------------------------------
                    # Avoid repeatedly writing 0
                    # ----------------------------------

                    self.last_throughput_time = (
                        time.time()
                    )

                # ======================================
                # Receive SSH data
                # ======================================

                if self.ssh_session.recv_ready():

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
                            f"SSH recv error: {repr(e)}"
                        )

                        time.sleep(0.2)

                        continue

                    if not data:
                        time.sleep(0.2)

                        continue

                    # ==================================
                    # Append received data
                    # ==================================

                    buffer += data

                    lines = buffer.split(
                        "\n"
                    )

                    buffer = lines[-1]

                    # ==================================
                    # Process complete lines
                    # ==================================

                    for line in lines[:-1]:

                        line = line.rstrip()

                        if not line:
                            continue

                        # ==================================
                        # Up-Time
                        #
                        # Example:
                        #
                        # ==== l1app [Time: 10/08/2026
                        # 13:03:45.959978]
                        # [Up-Time: 1Hr 7Min 15Sec]
                        # NumActiveCarrier: 2 ...
                        # ==================================

                        if "[Up-Time:" in line:

                            try:

                                uptime_start = (
                                    line.find(
                                        "[Up-Time:"
                                    )
                                )

                                uptime_end = (
                                    line.find(
                                        "]",
                                        uptime_start
                                    )
                                )

                                if (
                                        uptime_start
                                        != -1
                                        and
                                        uptime_end
                                        != -1
                                ):
                                    uptime = (
                                        line[
                                        uptime_start
                                        + len(
                                            "[Up-Time:"
                                        ):
                                        uptime_end
                                        ]
                                        .strip()
                                    )

                                    # ----------------------------------
                                    # Store current Up-Time
                                    # ----------------------------------

                                    self.uptime = (
                                        uptime
                                    )

                                    # print(
                                    #     "[Up-Time] "
                                    #     f"{self.uptime}"
                                    # )

                            except Exception as e:

                                print(
                                    "[Up-Time Parser ERROR] "
                                    f"{repr(e)}"
                                )

                        # ==================================
                        # Cell detection
                        # ==================================

                        if "0 (MU " in line:

                            cell_id = 0

                        elif "1 (MU " in line:

                            cell_id = 1

                        else:

                            continue

                        try:

                            # ==================================
                            # Split fields
                            # ==================================

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

                            # ==================================
                            # UL Throughput
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

                            # ==================================
                            # UL BLER
                            # ==================================

                            ul_bler = float(

                                ul_values[3]
                                .replace(
                                    "%",
                                    ""
                                )

                            )

                            # ==================================
                            # Update throughput timestamp
                            # ==================================

                            self.last_throughput_time = (
                                time.time()
                            )

                            # ==================================
                            # Store database
                            # ==================================

                            self.db.insert_throughput(

                                gnb_ip=(
                                    self.ip_address
                                ),

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

                            # ==================================
                            # Debug
                            # ==================================

                            timestamp = (
                                datetime.now()
                                .strftime(
                                    "%Y-%m-%d %H:%M:%S"
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

                        except Exception as e:

                            print(
                                "[Throughput Parser ERROR] "
                                f"{repr(e)}"
                            )

                            traceback.print_exc()

                # ==========================================
                # CPU protection
                # ==========================================

                time.sleep(0.2)

        except Exception as e:

            print(
                "[Throughput FATAL ERROR] "
                f"{repr(e)}"
            )

            traceback.print_exc()

            raise

    # =========================================================
    # Stop Throughput Monitor
    # =========================================================

    def stop_throughput_monitor(self):

        self.throughput_running = False

        if self.throughput_session:

            try:
                self.throughput_session.close()
            except Exception:
                pass

            self.throughput_session = None

    # =========================================================
    # Start All Monitors
    #
    # 建立 3 個獨立 SSH channel
    #
    # Channel 1 -> Throughput
    # Channel 2 -> Netconf
    # Channel 3 -> RU Manager
    # =========================================================

    def start_all_monitors(self):

        print(
            "[gNB Monitor] "
            "Starting all monitors..."
        )

        # ---------------------------------------------------------
        # Throughput
        # ---------------------------------------------------------

        self.start_throughput_monitor()

        # ---------------------------------------------------------
        # Netconf
        # ---------------------------------------------------------

        self.start_netconf_monitor()

        # ---------------------------------------------------------
        # RU Manager
        # ---------------------------------------------------------

        self.start_rumanager_monitor()

        print(
            "[gNB Monitor] "
            "All monitors started"
        )

    # =========================================================
    # Stop All Monitors
    # =========================================================

    def stop_all_monitors(self):

        print(
            "[gNB Monitor] "
            "Stopping all monitors..."
        )

        self.stop_throughput_monitor()

        self.stop_netconf_monitor()

        self.stop_rumanager_monitor()

        print(
            "[gNB Monitor] "
            "All monitors stopped"
        )
