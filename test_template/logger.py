import logging


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
