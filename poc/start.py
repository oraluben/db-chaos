from atexit import register
from pathlib import Path
from time import strftime

import yaml
from kubernetes import client, config, stream

dpl = Path(__file__).parent.resolve() / 'deployment.yaml'

if __name__ == '__main__':
    config.load_kube_config()
    app = client.AppsV1Api()

    with open(dpl) as f:
        d = yaml.load(f, Loader=yaml.FullLoader)
        d['metadata']['name'] += strftime("-%Y%m%d-%H%M%S")
        register(lambda: app.delete_namespaced_deployment(namespace='default', name=d['metadata']['name']))
    app.create_namespaced_deployment(namespace='default', body=d)

    core = client.CoreV1Api()

    ret = core.list_namespaced_pod(
        namespace='default',
        label_selector=','.join('{}={}'.format(*i) for i in d['metadata']['labels'].items()))

    for i in ret.items:
        print("%s\t%s\t%s" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name))

    # todo: run instances
    for i in ret.items:
        resp = stream.stream(core.connect_get_namespaced_pod_exec, namespace='default',
                             name=i.metadata.name, command=['/bin/sh', '-c', 'echo 0'],
                             stderr=True, stdin=False,
                             stdout=True, tty=False)
        print(resp)
