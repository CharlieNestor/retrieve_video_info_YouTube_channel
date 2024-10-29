import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger():
    """
    Function to set up the logger for the YouTube Data Tool.
    """
    # Create logs directory if it doesn't exist
    logs_dir = 'logs'
    os.makedirs(logs_dir, exist_ok=True)

    # Create a logger
    logger = logging.getLogger('youtube_data_tool')

    # Check if the logger already has handlers to avoid duplicates
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Create file handler with path in logs directory and custom naming pattern
        log_file = os.path.join(logs_dir, 'youtube_data_tool.log')
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=5*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.namer = lambda name: name.replace('.log.', '_') + '.log'
        file_handler.setLevel(logging.INFO)

        # Create console handler with a higher log level
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)

        # Create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add the handlers to the logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

# Create and export the logger
logger = setup_logger()