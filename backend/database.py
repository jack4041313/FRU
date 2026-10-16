import sqlite3
from pathlib import Path
from datetime import datetime


class GNBDatabase:

    def __init__(self):

        # =====================================================
        # Database path
        # =====================================================

        base_dir = (
            Path(__file__)
            .resolve()
            .parent
            .parent
        )

        db_dir = base_dir / "database"

        db_dir.mkdir(
            exist_ok=True
        )

        self.db_path = (
                db_dir / "gnb_monitor.db"
        )

        # =====================================================
        # SQLite connection
        # =====================================================

        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False
        )

        self.create_table()

        self.upgrade_database()

    # =========================================================
    # Create table
    # =========================================================

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

                dl_throughput REAL,

                ul_throughput REAL,

                ul_bler REAL
            )
            """
        )

        # =====================================================
        # Original time index
        # =====================================================

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_time
            ON throughput(timestamp)
            """
        )

        # =====================================================
        # gNB + Cell + Time index
        #
        # 多台 gNB 時查詢會使用到
        # =====================================================

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_gnb_cell_time
            ON throughput(
                gnb_ip,
                cell_id,
                timestamp
            )
            """
        )

        self.conn.commit()

    # =========================================================
    # Insert throughput
    # =========================================================

    def insert_throughput(
            self,
            gnb_ip,
            cell_id,
            dl_throughput,
            ul_throughput,
            ul_bler
    ):

        timestamp = (
            datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            )
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

    # =========================================================
    # Get latest throughput
    # =========================================================

    def get_latest_throughput(
            self,
            gnb_ip,
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

            WHERE gnb_ip = ?

            AND cell_id = ?

            ORDER BY id DESC

            LIMIT ?
            """,

            (
                gnb_ip,
                cell_id,
                limit
            )
        )

        rows = cursor.fetchall()

        # =====================================================
        # DESC → reverse
        # =====================================================

        rows.reverse()

        return [

            {
                "time": row[0],

                "value":
                    (
                        row[1]
                        if row[1] is not None
                        else 0
                    )
            }

            for row in rows

        ]

    # =========================================================
    # Delete old data
    # =========================================================

    def delete_old_data(self):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            DELETE FROM throughput

            WHERE timestamp <
            datetime(
                'now',
                'localtime',
                '-7 day'
            )
            """
        )

        self.conn.commit()

    # =========================================================
    # Get throughput history
    # =========================================================

    def get_throughput_history(
            self,
            gnb_ip,
            duration="10m",
            cell_id=None,
            column="dl_throughput"
    ):

        cursor = self.conn.cursor()

        # =====================================================
        # 防止 column 被任意傳入
        # =====================================================

        allowed_columns = [

            "dl_throughput",

            "ul_throughput",

            "ul_bler"

        ]

        if column not in allowed_columns:
            return []

        # =====================================================
        # Time range
        # =====================================================

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

        # =====================================================
        # 10m ~ 24h
        #
        # 保留所有原始資料
        # =====================================================

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

                WHERE gnb_ip = ?

                AND timestamp >= datetime(
                    'now',
                    'localtime',
                    ?
                )
            """

            params.extend(
                [
                    gnb_ip,

                    time_range[duration]
                ]
            )

            # =================================================
            # Cell filter
            # =================================================

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
        # 3 days
        #
        # 每分鐘取最低 throughput
        # =====================================================

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

                    WHERE gnb_ip = ?

                    AND timestamp >= datetime(
                        'now',
                        'localtime',
                        ?
                    )

            """

            params.extend(
                [
                    gnb_ip,

                    time_range[duration]
                ]
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

        # =====================================================
        # 7 days
        #
        # 每 5 分鐘取最低 throughput
        # =====================================================

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

                    WHERE gnb_ip = ?

                    AND timestamp >= datetime(
                        'now',
                        'localtime',
                        ?
                    )

            """

            params.extend(
                [
                    gnb_ip,

                    time_range[duration]
                ]
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

        # =====================================================
        # Execute
        # =====================================================

        cursor.execute(
            sql,
            params
        )

        rows = cursor.fetchall()

        # =====================================================
        # Convert result
        # =====================================================

        result = []

        for row in rows:

            value = row[1]

            if value is None:
                value = 0

            result.append(

                {

                    "time": row[0],

                    "value":
                        round(
                            value,
                            3
                        )

                }

            )

        return result

    # =========================================================
    # Upgrade existing database
    # =========================================================

    def upgrade_database(self):

        cursor = self.conn.cursor()

        # =====================================================
        # Get existing columns
        # =====================================================

        cursor.execute(
            """
            PRAGMA table_info(throughput)
            """
        )

        columns = [

            row[1]

            for row in cursor.fetchall()

        ]

        # =====================================================
        # Add gnb_ip if old DB doesn't have it
        # =====================================================

        if "gnb_ip" not in columns:
            cursor.execute(
                """
                ALTER TABLE throughput

                ADD COLUMN gnb_ip TEXT
                """
            )

        # =====================================================
        # Add UL throughput
        # =====================================================

        if "ul_throughput" not in columns:
            cursor.execute(
                """
                ALTER TABLE throughput

                ADD COLUMN ul_throughput REAL
                """
            )

        # =====================================================
        # Add UL BLER
        # =====================================================

        if "ul_bler" not in columns:
            cursor.execute(
                """
                ALTER TABLE throughput

                ADD COLUMN ul_bler REAL
                """
            )

        self.conn.commit()

        # =====================================================
        # Create index after upgrade
        # =====================================================

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_gnb_cell_time
            ON throughput(
                gnb_ip,
                cell_id,
                timestamp
            )
            """
        )

        self.conn.commit()
