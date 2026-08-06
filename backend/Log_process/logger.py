import logging
import datetime

execute_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(f"execute_log.txt", mode='a'),
        logging.StreamHandler()
    ]
)

logging.getLogger("werkzeug").setLevel(logging.ERROR)
logging.getLogger("paramiko").setLevel(logging.WARNING)