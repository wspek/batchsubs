"""
 Created by waldo on 3/15/17
"""

import logging

__author__ = "waldo"
__project__ = "batchsubs"


def get_logger(name):
    level = logging.DEBUG
    logger = logging.getLogger(name)
    # log_location = location

    logger.setLevel(level)

    # Create the handlers
    console_handler = logging.StreamHandler()  # Standard output handler
    # file_handler = logging.FileHandler(log_location, mode='w')

    # Set the log formatting
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(formatter)
    # file_handler.setFormatter(formatter)

    # Plugin the handlers
    logger.addHandler(console_handler)
    # logger.addHandler(file_handler)

    return logger
