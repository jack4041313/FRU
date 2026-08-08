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
        self.upgrade_database()

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
            dl_throughput,
            ul_throughput,
            ul_bler
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
                dl_throughput,
                ul_throughput,
                ul_bler
            )

            VALUES
            (?, ?, ?, ?, ?, ?)

            """,

            (
                timestamp,
                gnb_ip,
                cell_id,
                dl_throughput,
                ul_throughput,
                ul_bler
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
            cell_id=None,
            column="dl_throughput"
    ):

        cursor = self.conn.cursor()

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

        params = []

        # ==================================
        # 10m ~ 24h
        # 保留所有原始資料
        # ==================================

        if duration in [
            "10m",
            "1h",
            "3h",
            "6h",
            "12h",
            "24h"
        ]:

            sql = f"""

            SELECT

                timestamp,
                {column}


            FROM throughput


            WHERE timestamp >= datetime(
                'now',
                'localtime',
                ?
            )

            """

            params.append(
                time_range[duration]
            )

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



        # ==================================
        # 3 days
        # 每分鐘取最低 throughput
        # ==================================

        elif duration == "3d":

            sql = f"""

            WITH ranked AS
            (

                SELECT


                    timestamp,

                    {column},


                    ROW_NUMBER() OVER
                    (

                        PARTITION BY

                        strftime(
                            '%Y-%m-%d %H:%M',
                            timestamp
                        )


                        ORDER BY

                        {column} ASC

                    ) AS rn



                FROM throughput



                WHERE timestamp >= datetime(
                    'now',
                    'localtime',
                    ?
                )

            """

            params.append(
                time_range[duration]
            )

            if cell_id is not None:
                sql += """

                AND cell_id = ?

                """

                params.append(
                    cell_id
                )

            sql += f"""

            )


            SELECT

                timestamp,
                {column}


            FROM ranked


            WHERE rn = 1


            ORDER BY timestamp


            """



        # ==================================
        # 7 days
        # 每5分鐘取最低 throughput
        # ==================================

        elif duration == "7d":

            sql = f"""

            WITH ranked AS
            (

                SELECT


                    timestamp,

                    {column},


                    ROW_NUMBER() OVER
                    (

                        PARTITION BY


                        strftime(
                            '%Y-%m-%d %H',
                            timestamp
                        ),


                        CAST(
                            strftime(
                                '%M',
                                timestamp
                            ) AS INTEGER
                        ) / 5



                        ORDER BY

                        {column} ASC


                    ) AS rn



                FROM throughput



                WHERE timestamp >= datetime(
                    'now',
                    'localtime',
                    ?
                )

            """

            params.append(
                time_range[duration]
            )

            if cell_id is not None:
                sql += """

                AND cell_id = ?

                """

                params.append(
                    cell_id
                )

            sql += f"""

            )


            SELECT

                timestamp,
                {column}


            FROM ranked


            WHERE rn = 1


            ORDER BY timestamp


            """

        cursor.execute(
            sql,
            params
        )

        rows = cursor.fetchall()

        result = []

        for row in rows:
            result.append(

                {

                    "time": row[0],

                    "value":
                        round(
                            row[1]
                            if row[1] is not None
                            else 0,

                            3
                        )

                }

            )

        return result

    def upgrade_database(self):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            PRAGMA table_info(throughput)
            """
        )

        columns = [
            row[1]
            for row in cursor.fetchall()
        ]

        if "ul_throughput" not in columns:
            cursor.execute(
                """
                ALTER TABLE throughput
                ADD COLUMN ul_throughput REAL
                """
            )

        if "ul_bler" not in columns:
            cursor.execute(
                """
                ALTER TABLE throughput
                ADD COLUMN ul_bler REAL
                """
            )

        self.conn.commit()

