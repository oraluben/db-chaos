import logging
from typing import Optional

from kubernetes.client import AppsV1Api, CoreV1Api, NetworkingV1Api

from .logger import get_logger


class CoreV1ApiMixin:
    def __init__(self, api_core_v1: CoreV1Api, **kwargs):
        super().__init__(**kwargs)
        self.api_core_v1 = api_core_v1


class AppsV1ApiMixin:
    def __init__(self, api_apps_v1: AppsV1Api, **kwargs):
        super().__init__(**kwargs)
        self.api_apps_v1 = api_apps_v1


class NetworkingV1ApiMixin:
    def __init__(self, api_net_v1: NetworkingV1Api, **kwargs):
        super().__init__(**kwargs)
        self.api_net_v1 = api_net_v1


class LoggerMixin:
    def __init__(self, logger_name: Optional[str] = None, **kwargs) -> None:
        if logger_name is None:
            logger_name = self.__class__.__name__
        self.logger = get_logger(logger_name)
        self.logger.setLevel(logging.DEBUG)
        super().__init__(**kwargs)
