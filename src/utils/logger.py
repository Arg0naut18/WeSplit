import logging
from src.constants import LogConstants


logger = logging.getLogger(__name__)
logger.setLevel(LogConstants.LOG_LEVEL)

# Create a file handler
file_handler = logging.FileHandler(LogConstants.LOG_FILE)
file_handler.setLevel(LogConstants.LOG_LEVEL)

# Create a formatter and add it to the handler
formatter = logging.Formatter(LogConstants.LOG_MESSAGE_FORMAT)
file_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(file_handler)
