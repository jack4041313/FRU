"""PS2400 DU statistics monitor. Tracks timestamp-named rotating files over SSH."""
import re
import shlex
import threading
import time

from backend.database import GNBDatabase
from backend.ognb_component.base_server import server

LOG_DIR = "/nonvol_logs/log/pram"
FILE_PATTERN = re.compile(r"^du_stats_\d{2}(?:_\d{2}){5}\.txt$")
UE_PATTERN = re.compile(r"Total\s+Number\s+of\s+UEs\s*:\s*(\d+)")
SCH_PATTERN = re.compile(r"\bSCH\s+DL\s+Tpt\s*:\s*([\d.]+)\s+UL\s+Tpt\s*:?\s*([\d.]+)")


class PS2400Monitor(server):
    def __init__(self, ip_address, username, password, port=22):
        super().__init__(ip_address, username, password, port)
        self.db = GNBDatabase()
        self.stop_event = threading.Event()
        self.ue_count = None
        self.throughput_thread = None
        self._log_file = None
        self._offset = 0
        self._pending = ""
        self._initial_read = True

    def get_uptime(self):
        return "N/A"

    def _exec(self, command):
        _, stdout, stderr = self.ssh_client.exec_command(command, timeout=10)
        stdout.channel.settimeout(10)
        result = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace")
        if stdout.channel.recv_exit_status() != 0:
            raise RuntimeError(error.strip() or "PS2400 command failed")
        return result

    def _newest_log(self):
        # Filename timestamps have fixed-width components, so lexical order = chronological order.
        output = self._exec("find " + shlex.quote(LOG_DIR) +
                            " -maxdepth 1 -type f -name 'du_stats_*.txt' -printf '%f\\n' | sort -r | head -n 1")
        name = output.strip()
        return LOG_DIR + "/" + name if FILE_PATTERN.fullmatch(name) else None

    def _read_delta(self, path):
        quoted = shlex.quote(path)
        size = int(self._exec("stat -c %s -- " + quoted).strip())
        if size < self._offset:
            self._offset = 0
            self._pending = ""
        if self._initial_read:
            # On first connection read only the last 64 KiB, avoiding huge historic files.
            self._offset = max(0, size - 65536)
            self._initial_read = False
        if size == self._offset:
            return []
        # Limit a polling cycle to 64 KiB to avoid overwhelming SSH or the browser.
        end = min(size, self._offset + 65536)
        count = end - self._offset
        data = self._exec("tail -c +" + str(self._offset + 1) + " -- " + quoted +
                          " | head -c " + str(count))
        self._offset += len(data.encode("utf-8"))
        combined = self._pending + data
        lines = combined.split("\n")
        self._pending = lines.pop()
        return lines

    def scan_throughput(self):
        while not self.stop_event.is_set():
            try:
                latest = self._newest_log()
                if latest and latest != self._log_file:
                    self._log_file = latest
                    self._offset = 0
                    self._pending = ""
                    self._initial_read = True
                    print(f"[PS2400][{self.ip_address}] Monitoring {latest}")
                if latest:
                    for line in self._read_delta(latest):
                        ue = UE_PATTERN.search(line)
                        if ue:
                            self.ue_count = int(ue.group(1))
                        sch = SCH_PATTERN.search(line)
                        if sch:
                            self.db.insert_throughput(
                                gnb_ip=self.ip_address, cell_id=0,
                                dl_throughput=float(sch.group(1)),
                                ul_throughput=float(sch.group(2)), ul_bler=0)
            except Exception as exc:
                print(f"[PS2400][{self.ip_address}] Log polling failed: {exc}")
            self.stop_event.wait(3)

    def stop_all_monitors(self):
        self.stop_event.set()
        try:
            self.ssh_client.close()
        except Exception:
            pass
