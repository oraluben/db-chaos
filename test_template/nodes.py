from .logger import get_logger
from . import Node


class PdNode(Node):
    def start(self):
        len_pd = len(self.same_type_nodes)
        # starting from 1
        idx = self.index_of_env + 1
        pd_cmd = 'pd-server --name=pd{idx} --data-dir=pd' \
                 ' --client-urls=http://{pd_ip}:2379' \
                 ' --peer-urls=http://{pd_ip}:2380' \
                 ' --log-file=pd.log'.format(idx=idx, pd_ip=self.pod_ip)
        pd_cmd += ' --initial-cluster="{}"'.format(','.join(
            'pd{}=http://{}:2380'.format(i + 1, self.same_type_nodes[i].pod_ip)
            for i in range(len_pd)
        ))
        pd_cmd += ' -L "info"'
        get_logger(self.pod_name).debug('running `{}`'.format(pd_cmd))
        self.run_background_with_tmux(pd_cmd)


class KvNode(Node):
    def start(self):
        pd_ips = [i.pod_ip for i in self.env.node_instances[PdNode]]
        kv_cmd = 'tikv-server --pd="{pds}"' \
                 ' --addr="{kv_ip}:20160" --status-addr="{kv_ip}:20180"' \
                 ' --data-dir=tikv{idx}' \
                 ' --log-file=tikv.log'.format(pds=','.join('{}:2379'.format(i) for i in pd_ips),
                                               kv_ip=self.pod_ip, idx=self.index_of_env)
        get_logger(self.pod_name).debug('running `{}`'.format(kv_cmd))
        self.run_background_with_tmux(kv_cmd)


class DbNode(Node):
    def start(self):
        pd_ips = [i.pod_ip for i in self.env.node_instances[PdNode]]
        db_cmd = 'tidb-server --store=tikv' \
                 ' --path="{}"' \
                 ' --log-file=tidb.log'.format(','.join('{}:2379'.format(i) for i in pd_ips))
        get_logger(self.pod_name).debug('running `{}`'.format(db_cmd))
        self.run_background_with_tmux(db_cmd)
