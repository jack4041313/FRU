import time

from datetime import datetime
from backend.database import GNBDatabase
from backend.ognb_component.base_server import server


class ognb(server):

    def __init__(self, ip_address, username, password, port=22):
        super().__init__(ip_address, username, password, port)
        self.throughput_monitor = None
        self.db = GNBDatabase()
        self.last_throughput_time = time.time()

    def __del__(self):
        print('')

    def super_user(self):
        self.ssh_session.send("su\n")
        print(self.ssh_session.recv(2048).decode('utf-8').split('\n'))

        self.ssh_session.send("RAdisys@1234\n")
        print(self.ssh_session.recv(2048).decode('utf-8').split('\n'))

    def scan_throughput(
            self,
            log_path="/workspace/logs/l1_log_tdd"
    ):

        self.ssh_session.send(
            f"tail -F {log_path}\n"
        )

        buffer = ""

        while True:

            # ==========================
            # Check throughput timeout
            # ==========================

            if time.time() - self.last_throughput_time > 30:
                timestamp = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                print(
                    f"[{timestamp}] "
                    "No throughput data, gNB may crash"
                )

                # timeout 寫0

                self.db.insert_throughput(

                    gnb_ip=self.ip_address,

                    cell_id=1,

                    dl_throughput=0,

                    ul_throughput=0,

                    ul_bler=0

                )

                # 避免一直寫0

                self.last_throughput_time = time.time()

            # ==========================
            # Receive SSH data
            # ==========================

            if self.ssh_session.recv_ready():

                data = self.ssh_session.recv(
                    4096
                ).decode(
                    errors="ignore"
                )

                buffer += data

                lines = buffer.split("\n")

                buffer = lines[-1]

                for line in lines[:-1]:

                    # ----------------------
                    # Detect Cell
                    # ----------------------

                    if "0 (MU " in line:

                        cell_id = 0

                    elif "1 (MU " in line:

                        cell_id = 1


                    else:

                        continue

                    try:

                        parts = line.split("|")

                        # 欄位不足跳過

                        if len(parts) <= 4:
                            continue

                        # ======================
                        # DL Throughput
                        # MAC-to-PHY
                        # ======================

                        dl_field = parts[3].strip()

                        dl_throughput = (

                                float(

                                    dl_field
                                    .split()[0]
                                    .replace(",", "")

                                )

                                / 1000

                        )

                        # ======================
                        # UL Throughput + BLER
                        # PHY-to-MAC
                        # ======================

                        ul_field = parts[4].strip()

                        ul_values = ul_field.split()

                        if len(ul_values) < 4:
                            continue

                        ul_throughput = (

                                float(

                                    ul_values[0]
                                    .replace(",", "")

                                )

                                / 1000

                        )

                        ul_bler = float(

                            ul_values[3]
                            .replace("%", "")

                        )

                        # 更新時間

                        self.last_throughput_time = time.time()

                        # ======================
                        # Store DB
                        # ======================

                        self.db.insert_throughput(

                            gnb_ip=self.ip_address,

                            cell_id=cell_id,

                            dl_throughput=dl_throughput,

                            ul_throughput=ul_throughput,

                            ul_bler=ul_bler

                        )

                        timestamp = datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )

                        # print(
                        #
                        #     f"[{timestamp}] "
                        #
                        #     f"Cell-{cell_id} "
                        #
                        #     f"DL={dl_throughput:.3f} Mbps "
                        #
                        #     f"UL={ul_throughput:.3f} Mbps "
                        #
                        #     f"BLER={ul_bler:.2f}%"
                        #
                        # )

                    except (
                            IndexError,
                            ValueError
                    ):

                        continue

            # 避免 CPU 100%

            time.sleep(1)



