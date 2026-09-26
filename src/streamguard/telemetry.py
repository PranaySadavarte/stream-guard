import json
import logging
from logging.handlers import RotatingFileHandler


def event_logger(path):
    logger = logging.getLogger('streamguard.'+str(path))
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
    return logger


def masked_event(event):
    return {**event, 'term':event['term'][:1]+'***'}


def log_event(logger, event):
    logger.info(json.dumps(masked_event(event)))
