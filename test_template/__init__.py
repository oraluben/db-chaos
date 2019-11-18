from abc import ABC
from atexit import register
from random import choice
from time import sleep, strftime
from typing import List, Union, Type, Dict, Optional, TypeVar

from kubernetes import client, config
from kubernetes.client import CoreV1Api, V1Pod, AppsV1Api, V1PodList
from kubernetes.stream import stream

from .logger import init_logger
from .mixins import LoggerMixin, CoreV1ApiMixin, AppsV1ApiMixin

init_logger()

DEFAULT_NAMESPACE = 'default'


def label_selector(label_dict: Dict[str, str]) -> str:
    return ','.join('{}={}'.format(*i) for i in label_dict.items())


NodeType = Union[str, Type['Node']]


class Node(LoggerMixin, CoreV1ApiMixin, ABC):
    image: str
    name: str

    def __repr__(self) -> str:
        return '<{} as {}>'.format(self.pod_name, self.__class__.__qualname__)

    def is_type(self, other: NodeType):
        return self.name == (other if isinstance(other, str) else other.name)

    def __init__(self, api_core_v1: CoreV1Api, pod: V1Pod, env: 'TestBed', **kwargs):
        super().__init__(api_core_v1=api_core_v1, **kwargs)
        self._pod = pod
        self.env = env

    @property
    def pod_name(self) -> str:
        return self._pod.metadata.name

    @property
    def pod_ip(self) -> str:
        return self._pod.status.pod_ip

    @property
    def same_type_nodes(self):
        assert self.__class__ in self.env.node_instances
        return self.env.node_instances[self.__class__]

    @property
    def index_of_env(self):
        assert self in self.same_type_nodes
        return self.same_type_nodes.index(self)

    def run_background_with_tmux(self, cmd: str, session_name: Optional[str] = None):
        tmux_cmd = ['tmux', 'new-session', '-d', cmd]
        if session_name is not None:
            tmux_cmd += ['-s', session_name]
        self.logger.debug('running {}'.format(tmux_cmd))
        return stream(self.api_core_v1.connect_get_namespaced_pod_exec, namespace=DEFAULT_NAMESPACE,
                      name=self.pod_name, command=tmux_cmd,
                      stderr=True, stdin=False,
                      stdout=True, tty=False)

    def start(self):
        raise NotImplementedError()


class TestBed(LoggerMixin, CoreV1ApiMixin, AppsV1ApiMixin, ABC):
    label: Optional[Dict[str, str]] = None

    @staticmethod
    def node_def() -> Dict[Type[Node], int]:
        raise NotImplementedError()

    def create_deployment(self, node_count: int, wait_seconds=30, label: Optional[Dict[str, str]] = None) -> V1PodList:
        if label is None:
            label = {
                'dpl-random-pod-label': '0_{}_0'.format(hash(self))
            }
        self.label = label
        same_label_pods = self.api_core_v1.list_namespaced_pod(
            namespace=DEFAULT_NAMESPACE,
            label_selector=label_selector(label))
        assert len(same_label_pods.items) == 0

        dpl_name = 'dpl-name-{}'.format(strftime("%Y%m%d-%H%M%S"))

        dpl_template = {'apiVersion': 'apps/v1', 'kind': 'Deployment',
                        'metadata': {'name': dpl_name},
                        'spec': {'replicas': node_count,
                                 'selector': {'matchLabels': label},
                                 'template': {'metadata': {'labels': label},
                                              'spec': {
                                                  'containers': [
                                                      {'name': 'base', 'image': 'oraluben/tidb-poc',
                                                       'imagePullPolicy': 'Always',
                                                       'command': ['/bin/bash', '-c', '--'],
                                                       'args': ['sleep infinity']}]}}}}
        self.logger.info('creating deployment {}'.format(dpl_name))
        self.api_apps_v1.create_namespaced_deployment(namespace='default', body=dpl_template)

        register(lambda: self.api_apps_v1.delete_namespaced_deployment(
            namespace=DEFAULT_NAMESPACE, name=dpl_name))

        self.logger.info('waiting for pods')

        ret: Optional[V1PodList] = None
        for i in range(wait_seconds):
            ret = self.api_core_v1.list_namespaced_pod(
                namespace=DEFAULT_NAMESPACE,
                label_selector=label_selector(label))
            if len(ret.items) == node_count and all(i.status.phase == 'Running' for i in ret.items):
                break
            else:
                sleep(1)
        else:
            self.logger.error('pods not ready after {} seconds, got statuses: '.format(
                wait_seconds,
                [i.status.phase for i in ret.items]))
            assert False
        return ret

    node_instances: Dict[Type[Node], List[Node]]

    def __init__(self, api_core_v1: CoreV1Api, api_apps_v1: AppsV1Api, **kwargs):
        assert self.node_def
        super().__init__(api_core_v1=api_core_v1, api_apps_v1=api_apps_v1, **kwargs)

        self.node_instances = {}

        pods = self.create_deployment(sum(self.node_def().values()))

        for (t, c) in self.node_def().items():
            self.node_instances[t] = []
            for _ in range(c):
                self.node_instances[t].append(t(self.api_core_v1, pods.items.pop(), self))

    def start(self, interval: Optional[float] = None):
        for (t, l) in self.node_instances.items():
            for n in l:
                n.start()
                if interval is not None:
                    sleep(interval)


class TestAction(ABC):
    test_instance: 'Test'

    def __init__(self, test_instance: 'Test', **kwargs) -> None:
        super().__init__(**kwargs)
        self.test_instance = test_instance

    def run_action(self):
        raise NotImplementedError()

    @staticmethod
    def assert_(cond: bool, msg: Optional[str] = None):
        assert cond, msg


class Test(LoggerMixin, CoreV1ApiMixin, AppsV1ApiMixin, ABC):
    env_instance: TestBed

    @staticmethod
    def env() -> Type[TestBed]:
        raise NotImplementedError()

    def test_actions(self) -> List[Type[TestAction]]:
        raise NotImplementedError()

    def __init__(self, api_core_v1: CoreV1Api, api_apps_v1: AppsV1Api, **kwargs) -> None:
        super().__init__(api_core_v1=api_core_v1, api_apps_v1=api_apps_v1, **kwargs)
        self.env_instance = self.env()(api_core_v1=self.api_core_v1, api_apps_v1=api_apps_v1, **kwargs)

    def start(self):
        self.logger.info('initialing test environment')
        self._init_env()
        self.logger.info('test environment created')
        self.logger.info('start testing')
        self._run_test()
        self.logger.info('test finished, cleaning up...')

    def _init_env(self, env_init_interval: Optional[int] = None):
        self.env_instance.start(env_init_interval)

    def _run_test(self):
        for action in self.test_actions():
            action_instance = action(test_instance=self)
            self.logger.info('running {}'.format(action_instance.__class__.__name__))
            action_instance.run_action()
        from .chaos import ChaosManager
        ChaosManager(self.env_instance).stop()


V = TypeVar('V')


def pop_random(l: List[V]) -> Optional[V]:
    if not l:
        return None
    rand_idx = choice([i for i in range(len(l))])
    return l.pop(rand_idx)


def get_label(node: Node) -> Dict[str, str]:
    config.load_kube_config()
    client.CoreV1Api()
    return client.CoreV1Api().read_namespaced_pod(
        name=node.pod_name,
        namespace=DEFAULT_NAMESPACE).metadata.labels


def update_label(node: Node, labels: Dict[str, str]):
    config.load_kube_config()
    client.CoreV1Api()
    return client.CoreV1Api().patch_namespaced_pod(
        name=node.pod_name,
        namespace=DEFAULT_NAMESPACE,
        body={'metadata': {'labels': labels}})
