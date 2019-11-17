import logging
from typing import Optional


def init_logger():
    r = logging.getLogger()

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    ch.setFormatter(formatter)
    r.addHandler(ch)


def get_logger(name='__main__'):
    if name == '__main__':
        name = 'main'
    from logging import getLogger
    r = getLogger(name)
    r.setLevel(logging.DEBUG)
    return r


class LoggerMixin:
    def __init__(self, logger_name: Optional[str] = None, **kwargs) -> None:
        if logger_name is None:
            logger_name = self.__class__.__name__
        self.logger = get_logger(logger_name)
        self.logger.setLevel(logging.DEBUG)
        super().__init__(**kwargs)
