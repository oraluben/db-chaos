from atexit import register
from functools import partial
from pathlib import Path
from subprocess import run
from time import strftime, sleep

import yaml
from kubernetes import client, config
from kubernetes.client import V1PodList, CoreV1Api
from kubernetes.stream import stream

dpl = Path(__file__).parent.resolve() / 'deployment.yaml'


def run_background_in_tmux(api: CoreV1Api, name: str, cmd: str):
    return stream(api.connect_get_namespaced_pod_exec, namespace='default',
                  name=name, command=['tmux', 'new-session', '-d', cmd],
                  stderr=True, stdin=False,
                  stdout=True, tty=False)


def cleanup(api, deployment_name):
    print('cleaning up')
    api.delete_namespaced_deployment(namespace='default', name=deployment_name)


if __name__ == '__main__':
    config.load_kube_config()
    app = client.AppsV1Api()

    with open(dpl) as f:
        d = yaml.load(f, Loader=yaml.FullLoader)
        d['metadata']['name'] += strftime("-%Y%m%d-%H%M%S")
        register(partial(cleanup, api=app, deployment_name=d['metadata']['name']))
    app.create_namespaced_deployment(namespace='default', body=d)

    core = client.CoreV1Api()

    while True:
        ret: V1PodList = core.list_namespaced_pod(
            namespace='default',
            label_selector=','.join('{}={}'.format(*i) for i in d['metadata']['labels'].items()))
        if all(i.status.phase == 'Running' for i in ret.items):
            break
        else:
            sleep(1)

    name_ip = [(i.metadata.name, i.status.pod_ip) for i in ret.items]

    assert len(name_ip) == 4
    kvs = name_ip[:3]
    pd = name_ip[3]

    run_background_in_tmux(core, pd[0], 'pd-server --name=pd1 --data-dir=pd'
                                        ' --client-urls=http://{pd_ip}:2379'
                                        ' --peer-urls=http://{pd_ip}:2380'
                                        ' --initial-cluster="pd1=http://{pd_ip}:2380"'
                                        ' --log-file=pd.log'.format(pd_ip=pd[1]))

    for (kv_name, kv_ip) in kvs:
        run_background_in_tmux(core, kv_name, 'tikv-server --data-dir=tikv'
                                              ' --pd={pd_ip}:2379'
                                              ' --addr={kv_ip}:20160'
                                              ' --log-file=tikv.log'.format(pd_ip=pd[1], kv_ip=kv_ip))

    run_background_in_tmux(core, pd[0], 'tidb-server --store=tikv'
                                        ' --path={pd_ip}:2379'
                                        ' --log-file=tidb.log'.format(pd_ip=pd[1]))

    # wait for db
    mysql_probe = 'mysql -h {} -P 4000 -uroot -e "select tidb_version();"'.format(pd[1])
    for i in range(3):
        resp = stream(core.connect_get_namespaced_pod_exec, namespace='default',
                      name=pd[0], command=['bash', '-c', mysql_probe],
                      stderr=True, stdin=False,
                      stdout=True, tty=False)
        if 'tidb_version' in resp:
            print(resp)
            break
        sleep(3)
    else:
        run('kubectl exec -ti {} -- /bin/bash'.format(pd[0]), shell=True)
