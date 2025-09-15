# config.py
import os

CONFIG_FILE = "gestta_config.json"
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

DOWNLOAD_BASE_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_BASE_DIR, exist_ok=True)

DEBUG_MODE = False

# Credenciais para API Gestta
GESTTA_EMAIL = ""
GESTTA_PASSWORD = ""

# Variáveis globais para WinRAR
WINRAR_PATH = None
WINRAR_SEARCH_COMPLETED = False

# Definição de cores retrô
COLORS = {
    "purple": "#5d4777",
    "teal": "#2a9d8f",
    "yellow": "#e9c46a",
    "orange": "#f4a261",
    "red": "#e76f51",
    "dark_purple": "#29274c",
    "light_cream": "#f8ede3",
    "black": "#111111",
    "white": "#ffffff"
}
