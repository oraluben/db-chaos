from abc import ABC
from pathlib import Path
from subprocess import run
from typing import Type, Dict, List

from kubernetes import client, config
from kubernetes.stream import stream

from test_template import Test, TestBed, Node, DEFAULT_NAMESPACE, TestAction
from test_template.mixins import LoggerMixin


class SqlBenchEnv(TestBed):
    @staticmethod
    def node_def() -> Dict[Type[Node], int]:
        from test_template.nodes import PdNode, KvNode, DbNode
        return {
            PdNode: 3,
            KvNode: 3,
            DbNode: 1,
        }


class SsbBaseAction(TestAction, ABC):
    def __init__(self, test_instance: 'Test', **kwargs) -> None:
        super().__init__(test_instance, **kwargs)

        from test_template.nodes import DbNode
        self.db_node = self.test_instance.env_instance.node_instances[DbNode][0]

        self.bench_base = '/home/tidb/ssb'


class CopyBuildSsb(SsbBaseAction):
    def run_action(self):
        bench = Path(__file__).parent.resolve() / 'tidb-bench/ssb'
        run(['kubectl', 'cp', '{}'.format(bench),
             '{}/{}:{}'.format(DEFAULT_NAMESPACE, self.db_node.pod_name, '/home/tidb')])

        stream(self.test_instance.api_core_v1.connect_get_namespaced_pod_exec,
               namespace=DEFAULT_NAMESPACE, name=self.db_node.pod_name,
               command=['bash', '-c',
                        'cd {base}/dbgen && make -j && ./dbgen -s 1 -T a'.format(base=self.bench_base)],
               stderr=True, stdin=False,
               stdout=True, tty=False)

        print(self.db_node)


class SsbDbAndTable(SsbBaseAction):
    def run_action(self):
        stream(self.test_instance.api_core_v1.connect_get_namespaced_pod_exec,
               namespace=DEFAULT_NAMESPACE, name=self.db_node.pod_name,
               command=['bash', '-c',
                        'cd {base} && '
                        'mysql -h 127.0.0.1 -P 4000 -u root -e "drop database if exists ssb;" && '
                        'mysql -h 127.0.0.1 -P 4000 -u root -e "create database ssb;" && '
                        'mysql -h 127.0.0.1 -P 4000 -u root -D ssb < create_table.sql'.format(base=self.bench_base)],
               stderr=True, stdin=False,
               stdout=True, tty=False)


class SsbLoadData(LoggerMixin, SsbBaseAction):
    def run_action(self):
        load_sqls = [
            "mysql --local-infile=1 -h 127.0.0.1 -P 4000 -u root -D ssb -e"
            " \"load data local infile 'dbgen/{tb_name}.tbl'"
            " into table {tb_name} fields terminated by '|' lines terminated by '\\n';\"".format(tb_name=i)
            for i in ('part', 'supplier', 'customer', 'date', 'lineorder')
        ]

        for sql_cmd in load_sqls:
            self.logger.info('`{}`'.format(sql_cmd))
            stream(self.test_instance.api_core_v1.connect_get_namespaced_pod_exec,
                   namespace=DEFAULT_NAMESPACE, name=self.db_node.pod_name,
                   command=['bash', '-c',
                            'cd {base} && {sql}'.format(base=self.bench_base, sql=sql_cmd)],
                   stderr=True, stdin=False,
                   stdout=True, tty=False)


class SsbQuery(LoggerMixin, SsbBaseAction):
    def run_action(self):
        for i in range(1, 14):
            sql_cmd = 'mysql -h 127.0.0.1 -P 4000 -u root -D ssb < queries/{}.sql'.format(i)

            self.logger.info('`{}`'.format(sql_cmd))
            stream(self.test_instance.api_core_v1.connect_get_namespaced_pod_exec,
                   namespace=DEFAULT_NAMESPACE, name=self.db_node.pod_name,
                   command=['bash', '-c',
                            'cd {base} && {sql}'.format(base=self.bench_base, sql=sql_cmd)],
                   stderr=True, stdin=False,
                   stdout=True, tty=False)


class SqlBenchTest(Test):
    @staticmethod
    def test_action_instances() -> List[Type[TestAction]]:
        return [
            CopyBuildSsb,
            SsbDbAndTable,
            SsbLoadData,
            SsbQuery,
        ]

    @staticmethod
    def env() -> Type[TestBed]:
        return SqlBenchEnv


if __name__ == '__main__':
    config.load_kube_config()
    SqlBenchTest(api_core_v1=client.CoreV1Api(), api_apps_v1=client.AppsV1Api()).start()
