from backend.database import GNBDatabase


db = GNBDatabase()


db.insert_throughput(
    "10.255.174.7",
    300.223
)