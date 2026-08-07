import sqlite3
from pathlib import Path
from datetime import datetime


class GNBDatabase:

    def __init__(self):
        base_dir = Path(__file__).resolve().parent.parent

        db_dir = base_dir / "database"

        db_dir.mkdir(
            exist_ok=True
        )

        self.db_path = db_dir / "gnb_monitor.db"

        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False
        )

        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS throughput
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp TEXT,

                gnb_ip TEXT,

                cell_id INTEGER,

                dl_throughput REAL
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_time

            ON throughput(timestamp)

            """
        )

        self.conn.commit()

    def insert_throughput(
            self,
            gnb_ip,
            cell_id,
            throughput
    ):
        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT INTO throughput
            (
                timestamp,
                gnb_ip,
                cell_id,
                dl_throughput
            )

            VALUES
            (?, ?, ?, ?)

            """,

            (
                timestamp,
                gnb_ip,
                cell_id,
                throughput
            )
        )

        self.conn.commit()

    def get_latest_throughput(
            self,
            cell_id,
            limit=1000
    ):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT

                timestamp,
                dl_throughput

            FROM throughput

            WHERE cell_id = ?

            ORDER BY id DESC

            LIMIT ?

            """,

            (
                cell_id,
                limit
            )
        )

        rows = cursor.fetchall()

        # 因為 DESC 取資料
        # 需要反轉成時間由舊到新

        rows.reverse()

        return [

            {
                "time": row[0],
                "value": row[1]
            }

            for row in rows

        ]

    def delete_old_data(self):
        cursor = self.conn.cursor()

        cursor.execute(
            """
            DELETE FROM throughput

            WHERE timestamp <
            datetime('now','-7 day')

            """
        )

        self.conn.commit()

    def get_throughput_history(
            self,
            duration="10m",
            cell_id=None
    ):

        cursor = self.conn.cursor()

        # 時間範圍
        time_range = {

            "10m": "-10 minute",

            "1h": "-1 hour",

            "3h": "-3 hour",

            "6h": "-6 hour",

            "12h": "-12 hour",

            "24h": "-1 day",

            "3d": "-3 day",

            "7d": "-7 day"

        }

        if duration not in time_range:
            return []

        # =====================================================
        # 10 minutes (顯示每一筆資料)
        # =====================================================

        if duration == "10m":

            sql = """
            SELECT

                timestamp,

                dl_throughput

            FROM throughput

            WHERE timestamp >= datetime(
                'now',
                'localtime',
                ?
            )
            """

            params = [
                time_range[duration]
            ]

            if cell_id is not None:
                sql += """

                AND cell_id = ?

                """

                params.append(
                    cell_id
                )

            sql += """

            ORDER BY timestamp

            """

        # =====================================================
        # 1h ~ 24h (每分鐘平均)
        # =====================================================

        elif duration in [
            "1h",
            "3h",
            "6h",
            "12h",
            "24h"
        ]:

            sql = """
            SELECT

                strftime(
                    '%Y-%m-%d %H:%M',
                    timestamp
                ) AS time,

                AVG(dl_throughput)

            FROM throughput

            WHERE timestamp >= datetime(
                'now',
                'localtime',
                ?
            )
            """

            params = [
                time_range[duration]
            ]

            if cell_id is not None:
                sql += """

                AND cell_id = ?

                """

                params.append(
                    cell_id
                )

            sql += """

            GROUP BY time

            ORDER BY time

            """

        # =====================================================
        # 3d、7d (每小時平均)
        # =====================================================

        else:

            sql = """
            SELECT

                strftime(
                    '%Y-%m-%d %H',
                    timestamp
                ) AS time,

                AVG(dl_throughput)

            FROM throughput

            WHERE timestamp >= datetime(
                'now',
                'localtime',
                ?
            )
            """

            params = [
                time_range[duration]
            ]

            if cell_id is not None:
                sql += """

                AND cell_id = ?

                """

                params.append(
                    cell_id
                )

            sql += """

            GROUP BY time

            ORDER BY time

            """

        cursor.execute(
            sql,
            params
        )

        rows = cursor.fetchall()

        return [

            {

                "time": row[0],

                "value": round(
                    row[1],
                    3
                ) if row[1] is not None else 0

            }

            for row in rows

        ]