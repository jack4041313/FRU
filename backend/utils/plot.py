import time
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from queue import Queue

class ThroughputMonitor:

    def __init__(self):

        self.throughput_queue = Queue()

        self.times = []
        self.values = []

        # 建立 Figure (只建立一次)
        self.fig, self.ax = plt.subplots(figsize=(10, 5))

        self.line, = self.ax.plot(
            [],
            [],
            marker="o",
            linewidth=2
        )

        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("DL Throughput (kbps)")
        self.ax.set_title("Real-Time DL Throughput")
        self.ax.grid(True)

        # X 軸顯示時間格式
        self.ax.xaxis.set_major_formatter(
            mdates.DateFormatter("%H:%M:%S")
        )

    def add_data_bk(self, timestamp, throughput):

        self.throughput_queue.put(
            (timestamp, throughput)
        )

    def add_data(
            self,
            timestamp,
            throughput
    ):

        throughput_data.append(
            {
                "time": timestamp,
                "value": throughput
            }
        )

    def update_plot(self):

        updated = False

        while not self.throughput_queue.empty():

            timestamp, value = self.throughput_queue.get()

            self.times.append(timestamp)
            self.values.append(value)

            updated = True

        if not updated:
            return

        self.line.set_data(
            self.times,
            self.values
        )

        self.ax.relim()
        self.ax.autoscale_view()

        self.fig.autofmt_xdate()

        self.fig.canvas.draw_idle()

    def realtime_plot(self):

        plt.ion()

        plt.show(block=False)

        last_update = time.time()

        while plt.fignum_exists(self.fig.number):

            # 讓 GUI 持續處理事件 (視窗才不會卡住)
            plt.pause(0.1)

            # 每 60 秒更新一次資料
            if time.time() - last_update >= 60:

                self.update_plot()

                last_update = time.time()


"""
class ThroughputMonitor:

    def __init__(self):

        self.throughput_queue = Queue()

        self.times = []
        self.values = []

    def add_data(self, timestamp, throughput):

        self.throughput_queue.put(
            (
                timestamp,
                throughput
            )
        )

    def realtime_plot(self):

        fig, ax = plt.subplots()

        line, = ax.plot(
            [],
            [],
            marker="o"
        )

        def update(frame):

            while not self.throughput_queue.empty():
                timestamp, value = (
                    self.throughput_queue.get()
                )

                self.times.append(timestamp)
                self.values.append(value)

            if self.times:
                line.set_data(
                    self.times,
                    self.values
                )

                ax.relim()
                ax.autoscale_view()

                # 設定時間格式
                ax.xaxis.set_major_formatter(
                    mdates.DateFormatter("%H:%M:%S")
                )

                fig.autofmt_xdate()

            return line,

        self.ani = animation.FuncAnimation(
            fig,
            update,
            interval=1000
        )

        ax.set_xlabel("Time")
        ax.set_ylabel("DL Throughput (kbps)")
        ax.set_title("Real Time DL Throughput")

        plt.grid()

        plt.show()
"""
