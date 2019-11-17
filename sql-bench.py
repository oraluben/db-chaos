from pathlib import Path
from subprocess import run
from typing import Type, Dict

from kubernetes import client, config
from kubernetes.stream import stream

from test_template import Test, TestBed, Node, DEFAULT_NAMESPACE


class SqlBenchEnv(TestBed):
    @staticmethod
    def node_def() -> Dict[Type[Node], int]:
        from test_template.nodes import PdNode, KvNode, DbNode
        return {
            PdNode: 3,
            KvNode: 3,
            DbNode: 1,
        }


class SqlBenchTest(Test):
    @staticmethod
    def env() -> Type[TestBed]:
        return SqlBenchEnv

    def _run_test(self):
        from test_template.nodes import DbNode
        db_node = self.env_instance.node_instances[DbNode][0]

        bench = Path(__file__).parent.resolve() / 'tidb-bench/ssb'
        run(['kubectl', 'cp', '{}'.format(bench),
             '{}/{}:{}'.format(DEFAULT_NAMESPACE, db_node.pod_name, '/home/tidb')])

        bench_base = '/home/tidb/ssb'

        resp = stream(self.api_core_v1.connect_get_namespaced_pod_exec,
                      namespace=DEFAULT_NAMESPACE, name=db_node.pod_name,
                      command=['bash', '-c',
                               'cd {base}/dbgen && make -j && ./dbgen -s 1 -T a'.format(base=bench_base)],
                      stderr=True, stdin=False,
                      stdout=True, tty=False)
        print(resp)

        print(db_node.pod_name)
        run('bash', shell=True)


if __name__ == '__main__':
    config.load_kube_config()
    SqlBenchTest(api_core_v1=client.CoreV1Api(), api_apps_v1=client.AppsV1Api()).start()
