from functools import partial
from typing import Dict, Type, Optional, List

from kubernetes import config, client
from kubernetes.stream import stream

from test_template import Test, TestBed, Node, DEFAULT_NAMESPACE, TestAction
from test_template.actions import SleepAction


class FakeEnv(TestBed):
    @staticmethod
    def node_def() -> Dict[Type[Node], int]:
        from test_template.nodes import PdNode, KvNode, DbNode
        return {
            PdNode: 3,
            KvNode: 3,
            DbNode: 1,
        }


class FakeAction(TestAction):
    def run_action(self):
        from test_template.nodes import DbNode
        db_nodes = self.test_instance.env_instance.node_instances[DbNode]
        assert len(db_nodes) == 1

        mysql_probe = 'mysql -h {} -P 4000 -uroot -e "select tidb_version();"'.format(db_nodes[0].pod_ip)
        resp = stream(self.test_instance.env_instance.api_core_v1.connect_get_namespaced_pod_exec,
                      namespace=DEFAULT_NAMESPACE, name=db_nodes[0].pod_name,
                      command=['bash', '-c', mysql_probe],
                      stderr=True, stdin=False,
                      stdout=True, tty=False)
        self.assert_('tidb_version' in resp, resp)


class FakeTest(Test):
    @staticmethod
    def test_action_instances() -> List[Type[TestAction]]:
        return [
            partial(SleepAction, sleep_interval=10),
            FakeAction,
        ]

    @staticmethod
    def env() -> Type[TestBed]:
        return FakeEnv

    def _init_env(self, env_init_interval: Optional[int] = 1):
        super()._init_env(env_init_interval)


if __name__ == '__main__':
    config.load_kube_config()
    FakeTest(api_core_v1=client.CoreV1Api(), api_apps_v1=client.AppsV1Api()).start()
