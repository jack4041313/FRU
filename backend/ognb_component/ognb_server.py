from datetime import datetime
from backend.database import GNBDatabase
from backend.ognb_component.base_server import server


class ognb(server):

    def __init__(self, ip_address, username, password, port=22):
        super().__init__(ip_address, username, password, port)
        self.throughput_monitor = None
        self.db = GNBDatabase()

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

        while True:
            if self.ssh_session.recv_ready():

                data = self.ssh_session.recv(4096).decode()
                for line in data.splitlines():

                    if "1 (MU " in line:

                        try:
                            # print(line)
                            parts = line.split("|")

                            # MAC-to-PHY Tput 欄位
                            tput_field = parts[3].strip()

                            # 第一個值就是 DL throughput
                            throughput = float(tput_field.split()[0].replace(",", "")) / 1000

                            timestamp = datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )

                            self.db.insert_throughput(
                                gnb_ip=self.ip_address,
                                cell_id=1,
                                throughput=throughput
                            )

                            print(
                                f"[{timestamp}] DL Throughput = {throughput:.3f} Mbps"
                            )
                            
                        except (IndexError, ValueError) as e:

                            print(
                                f"Skip invalid throughput line: {line}"
                            )
                            continue



"""
# real-time
def scan_throughput(self, log_path="/workspace/logs/l1_log_tdd"):
    self.ssh_session.send(f"tail -F {log_path}\n")

    while True:
        if self.ssh_session.recv_ready():
            data = self.ssh_session.recv(4096).decode()

            # print raw log
            # print(data, end="\n")

            for line in data.splitlines():
                # print cell 1 throughput
                if "1 (MU" in line:
                    line = line.strip()
                    match = re.search(
                        r'\|\s+\d+,\s+\d+\s+\|\s+(\d+)\s+\d+\s+\|',
                        line
                    )

                    if match:
                        throughput = int(
                            match.group(1)
                        )

                        timestamp = datetime.now()

                        # 丟給 plot thread
                        self.throughput_monitor.add_data(
                                timestamp,
                                throughput
                        )

                        print(
                            f"[{timestamp}] "
                            f"DL Throughput={throughput} kbps"
                        )
"""