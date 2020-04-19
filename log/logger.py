import logging
import time
import os
import functools

import settings


class CustomLogger:
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    INFO = logging.INFO
    DEBUG = logging.DEBUG

    FILE_PATH = settings.get('logger_file_path', 'app.log')
    FILE_LOG_LEVEL = getattr(logging, settings.get('logger_file_log_level', 'INFO').upper())
    STDOUT_LOG_LEVEL = getattr(logging, settings.get('logger_stdout_log_level', 'WARNING').upper())

    def __init__(self):
        self._logger = None
        self._setup()

        self.error = functools.partial(self.log, self.ERROR)
        self.warning = functools.partial(self.log, self.WARNING)
        self.info = functools.partial(self.log, self.INFO)
        self.debug = functools.partial(self.log, self.DEBUG)

    def _setup(self):
        self._logger = logging.getLogger()
        self._logger.setLevel(logging.WARNING)

        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%d.%m.%Y %H:%M:%S')

        fh = logging.FileHandler(self.FILE_PATH)
        fh.setFormatter(formatter)
        fh.setLevel(self.FILE_LOG_LEVEL)
        self._logger.addHandler(fh)

        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        sh.setLevel(self.STDOUT_LOG_LEVEL)
        self._logger.addHandler(sh)
        self._logger.setLevel(min(self.FILE_LOG_LEVEL, self.STDOUT_LOG_LEVEL))

    def log(self, level, text, exc_info=False, start_time=None, show_pid=False):
        if start_time:
            text = f'{text} {int((time.time() - start_time) * 1000)}ms'
        if show_pid:
            text = f'pid{os.getpid()}: {text}'

        self._logger.log(level, f'{text} ', exc_info=exc_info)
