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

    def scan_throughput(self, log_path="/workspace/logs/l1_log_tdd"):

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

                throughput = 0

                print(
                    f"[{timestamp}] "
                    "No throughput data, gNB may crash"
                )

                self.db.insert_throughput(
                    gnb_ip=self.ip_address,
                    cell_id=1,
                    throughput=throughput
                )

                # 避免每秒一直寫0
                self.last_throughput_time = time.time()

            # ==========================
            # Receive SSH data
            # ==========================
            if self.ssh_session.recv_ready():

                data = self.ssh_session.recv(4096).decode()

                buffer += data

                lines = buffer.split("\n")

                buffer = lines[-1]

                for line in lines[:-1]:

                    if "0 (MU " in line:
                        cell_id = 0

                    elif "1 (MU " in line:
                        cell_id = 1

                    else:
                        continue

                    try:

                        parts = line.split("|")

                        if len(parts) <= 3:
                            continue

                        tput_field = parts[3].strip()

                        throughput = (
                                float(
                                    tput_field
                                    .split()[0]
                                    .replace(",", "")
                                )
                                / 1000
                        )

                        self.last_throughput_time = time.time()

                        self.db.insert_throughput(
                            gnb_ip=self.ip_address,
                            cell_id=cell_id,
                            throughput=throughput
                        )

                        timestamp = datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )

                        print(
                            f"[{timestamp}] "
                            f"Cell-{cell_id} DL Throughput = {throughput:.3f} Mbps"
                        )

                    except (IndexError, ValueError):

                        continue

            # 避免 CPU 100%
            time.sleep(1)



