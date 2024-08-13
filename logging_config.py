import logging
from logging.handlers import RotatingFileHandler

def setup_logger():
    """
    Function to set up the logger for the YouTube Data Tool.
    """
    # Create a logger
    logger = logging.getLogger('youtube_data_tool')
    logger.setLevel(logging.INFO)

    # Create file handler which logs messages from INFO level upwards
    file_handler = RotatingFileHandler('youtube_data_tool.log', maxBytes=5*1024*1024, backupCount=2)
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