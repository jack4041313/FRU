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
            limit=1000
    ):
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT

                timestamp,
                dl_throughput

            FROM throughput

            ORDER BY id DESC

            LIMIT ?

            """,

            (
                limit,
            )
        )

        rows = cursor.fetchall()

        # 時間排序由舊到新

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
            duration="10m"
    ):

        cursor = self.conn.cursor()

        if duration == "10m":

            sql = """
            SELECT
                timestamp,
                dl_throughput

            FROM throughput

            WHERE timestamp >= datetime(
                'now',
                'localtime',
                '-10 minute'
            )

            ORDER BY timestamp
            """

        elif duration == "1h":

            sql = """
            SELECT

                strftime(
                    '%Y-%m-%d %H:%M',
                    timestamp
                ),

                AVG(dl_throughput)


            FROM throughput


            WHERE timestamp >= datetime(
                'now',
                'localtime',
                '-1 hour'
            )


            GROUP BY 1

            ORDER BY 1
            """

        elif duration == "3h":

            sql = """
            SELECT

                strftime(
                    '%Y-%m-%d %H:%M',
                    timestamp
                ),

                AVG(dl_throughput)


            FROM throughput


            WHERE timestamp >= datetime(
                'now',
                'localtime',
                '-3 hour'
            )


            GROUP BY 1

            ORDER BY 1
            """

        elif duration == "6h":

            sql = """
            SELECT

                strftime(
                    '%Y-%m-%d %H:%M',
                    timestamp
                ),

                AVG(dl_throughput)


            FROM throughput


            WHERE timestamp >= datetime(
                'now',
                'localtime',
                '-6 hour'
            )


            GROUP BY 1

            ORDER BY 1
            """

        elif duration == "12h":

            sql = """
            SELECT

                strftime(
                    '%Y-%m-%d %H:%M',
                    timestamp
                ),

                AVG(dl_throughput)


            FROM throughput


            WHERE timestamp >= datetime(
                'now',
                'localtime',
                '-12 hour'
            )


            GROUP BY 1

            ORDER BY 1
            """

        elif duration == "24h":

            sql = """
            SELECT

                strftime(
                    '%Y-%m-%d %H:%M',
                    timestamp
                ),

                AVG(dl_throughput)


            FROM throughput


            WHERE timestamp >= datetime(
                'now',
                'localtime',
                '-1 day'
            )


            GROUP BY 1

            ORDER BY 1
            """

        elif duration == "3d":

            sql = """
            SELECT

                strftime(
                    '%Y-%m-%d %H',
                    timestamp
                ),

                AVG(dl_throughput)


            FROM throughput


            WHERE timestamp >= datetime(
                'now',
                'localtime',
                '-3 day'
            )


            GROUP BY 1

            ORDER BY 1
            """

        elif duration == "7d":

            sql = """
            SELECT

                strftime(
                    '%Y-%m-%d %H',
                    timestamp
                ),

                AVG(dl_throughput)


            FROM throughput


            WHERE timestamp >= datetime(
                'now',
                'localtime',
                '-7 day'
            )


            GROUP BY 1

            ORDER BY 1
            """

        else:

            return []

        cursor.execute(sql)

        rows = cursor.fetchall()

        return [

            {
                "time": row[0],
                "value": round(row[1], 3)
            }

            for row in rows

        ]
