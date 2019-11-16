from typing import Dict, Type, Optional

from kubernetes import config, client
from kubernetes.stream import stream

from . import Test, TestBed, Node, DEFAULT_NAMESPACE


class FakeEnv(TestBed):
    @classmethod
    def node_def(cls) -> Dict[Type[Node], int]:
        from .nodes import PdNode, KvNode, DbNode
        return {
            PdNode: 3,
            KvNode: 3,
            DbNode: 1,
        }


class FakeTest(Test):
    @staticmethod
    def env() -> Type[TestBed]:
        return FakeEnv

    def _init_env(self, env_init_interval: Optional[int] = 1):
        super()._init_env(env_init_interval)

    def _run_test(self):
        from .nodes import DbNode
        db_nodes = self.env_instance.node_instances[DbNode]
        assert len(db_nodes) == 1

        from time import sleep
        sleep(10)
        mysql_probe = 'mysql -h {} -P 4000 -uroot -e "select tidb_version();"'.format(db_nodes[0].pod_ip)
        resp = stream(self.api_core_v1.connect_get_namespaced_pod_exec, namespace=DEFAULT_NAMESPACE,
                      name=db_nodes[0].pod_name, command=['bash', '-c', mysql_probe],
                      stderr=True, stdin=False,
                      stdout=True, tty=False)
        assert 'tidb_version' in resp, resp


if __name__ == '__main__':
    config.load_kube_config()
    FakeTest(api_core_v1=client.CoreV1Api(), api_apps_v1=client.AppsV1Api()).start()
