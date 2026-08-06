import time
import paramiko

from backend.Log_process.logger import logging
from paramiko.ssh_exception import (NoValidConnectionsError, AuthenticationException, ChannelException, SSHException)


def delay_decorator(func):
    def wrapper(*args, **kwargs):
        func(*args, **kwargs)
        time.sleep(2)

    return wrapper


class server:
    def __init__(self, ip_address, username, password, port=22):
        self.ip_address = ip_address
        self.username = username
        self.password = password
        self.port = port

        self.ssh_client = None
        self.ssh_session = None
        self.channel = None

    @delay_decorator
    def connect(self):
        logging.info(f"Connect server {self.ip_address}")

        try:
            # logging.info(f"Connect to server {self.ip_address}")
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # 連接到SSH伺服器

            self.ssh_client.connect(
                self.ip_address, port=self.port, username=self.username, password=self.password
            )
            self.ssh_session = self.ssh_client.invoke_shell()
            time.sleep(5)

        except NoValidConnectionsError as e:
            logging.error("[ERROR] Connect failure, ensure SSH is enabled: ", e)
        except ChannelException as e:
            logging.error("[ERROR] Channel connection failure : ", e)
        except AuthenticationException as e:
            logging.error("[ERROR] Username & Password error: ", e)
        except SSHException as e:
            logging.error("[ERROR] SSH Session failure : ", e)

    def clear_recv_buffer(self, channel, bufsize=1024):
        """
        清空 Paramiko 通道的 recv 緩衝區
        :param channel: SSH 通道（例如 stdout.channel 或 stderr.channel）
        :param bufsize: 每次讀取的位元組數（默認 1024）
        """
        while channel.recv_ready():  # 檢查是否有數據可讀取
            channel.recv(bufsize)

    @delay_decorator
    def disconnect(self):
        logging.info(f"Disconnect server {self.ip_address}")

        try:
            if self.ssh_session:
                self.ssh_session.close()
        except Exception:
            logging.exception("Failed to close ssh_session")

        try:
            if self.ssh_client:
                self.ssh_client.close()
        except Exception:
            logging.exception("Failed to close ssh_client")

        self.ssh_session = None
        self.ssh_client = None

    @delay_decorator
    def exit(self):
        logging.info("exit...")
        self.ssh_session.send('exit\n')

