import logging
import sys
import os
from datetime import datetime

def configure_logging():
    """Configure logging with proper Unicode support"""
    # Set console encoding to UTF-8 if possible
    if sys.stdout.isatty():
        try:
            # For Windows console
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleOutputCP(65001)  # Set to UTF-8
        except (AttributeError, ImportError):
            pass
    
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Get current date for log filename
    current_date = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'logs/app_{current_date}.log'
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers if any
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
    
    # File handler - explicitly use UTF-8 encoding
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # Console handler with error handling for encoding issues
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
