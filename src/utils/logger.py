import logging
from logging.handlers import RotatingFileHandler
import sys
from config.config import LogConfig

def setup_logger(config: LogConfig):
    logger = logging.getLogger('iot_debug')
    logger.setLevel(getattr(logging, config.log_level.upper()))
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    file_handler = RotatingFileHandler(
        config.log_file,
        maxBytes=config.max_file_size,
        backupCount=config.backup_count
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

class LogBuffer:
    def __init__(self, max_lines: int = 1000):
        self.buffer = []
        self.max_lines = max_lines
    
    def add(self, message: str):
        self.buffer.append(message)
        if len(self.buffer) > self.max_lines:
            self.buffer.pop(0)
    
    def get_all(self) -> list:
        return self.buffer.copy()
    
    def clear(self):
        self.buffer.clear()
