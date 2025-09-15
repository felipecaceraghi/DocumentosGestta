# logger_config.py
import logging
import os
from config import LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "gestta_system.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("GesttaSystem")
