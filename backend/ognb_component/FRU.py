import time

from backend.Log_process.logger import logging


class PR2420:
    def __init__(self, ip_address, session):
        self.ip_address = ip_address
        self.ssh_session = session

    def connect(self):
        error_count = 0
        while True:
            logging.info(f"Login PR2420 {self.ip_address}")
            self.ssh_session.send(f"ssh root@{self.ip_address}\n")
            time.sleep(5)

            output_lines = self.ssh_session.recv(65535).decode('utf-8').split('\n')
            if 'Are you sure you want to continue connecting (yes/no/[fingerprint])? ' in output_lines:
                self.ssh_session.send(f"yes\n")
                time.sleep(5)

            # PR2420 need password
            if "password:" in output_lines[-1]:
                self.ssh_session.send("12345\n")
                time.sleep(3)
                output_lines = self.ssh_session.recv(2048).decode('utf-8').split('\n')

            if 'PR1450# ' in output_lines:
                break

            error_count += 1
            if error_count == 15:
                raise Exception(f"Login PR1400 {self.ip_address} fail 10 times, please check your setting.")

    def restart(self):
        logging.info("restart...")
        self.ssh_session.send('reboot\u000d')
        time.sleep(3)

        # Are you sure to reboot?
        self.ssh_session.send('y\n')
        time.sleep(3)

    def disconnect(self):
        logging.info("logout...")
        self.ssh_session.send('logout\n')
        time.sleep(3)