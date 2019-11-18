from atexit import register
from random import choice
from typing import Union, Type, Optional, Dict

from test_template import Node, DEFAULT_NAMESPACE
from test_template.chaos import ChaosOperator, ChaosManager
from test_template.mixins import NetworkingV1ApiMixin, LoggerMixin

"""
Operator class: A kind of actions
Operator instance: one action can be executed during test, can have multiple instance in one test.
"""


class NodeOffline(NetworkingV1ApiMixin, LoggerMixin, ChaosOperator):
    @property
    def can_activate(self) -> bool:
        return self.offline_node is None

    @property
    def can_deactivate(self) -> bool:
        return self.offline_node is not None

    def activate(self):
        assert self.can_activate
        nodes = sum(self._mgr.env.node_instances.values(), [])

        # todo: abstract node selection
        same_type_node_idx = [i for i in range(len(nodes)) if nodes[i].is_type(self.node_type)]
        assert same_type_node_idx, 'no nodes of type {}'.format(self.node_type)
        self.offline_node = nodes.pop(choice(same_type_node_idx))

        old_labels: Dict[str, str] = self._mgr.env.api_core_v1.read_namespaced_pod(
            name=self.offline_node.pod_name,
            namespace=DEFAULT_NAMESPACE).metadata.labels
        self.offline_label_key = 'random-offline-label_{}_0'.format(hash(self))

        new_label = {self.offline_label_key: '0_{}_0'.format(hash(self))}
        old_labels.update(new_label)
        self._mgr.env.api_core_v1.patch_namespaced_pod(
            name=self.offline_node.pod_name,
            namespace=DEFAULT_NAMESPACE,
            body={'metadata': {'labels': old_labels}})

        tmp_np_name = 'np-deny-all-{}'.format(hash(self))
        deny_all_policy = {'apiVersion': 'networking.k8s.io/v1',
                           'kind': 'NetworkPolicy',
                           'metadata': {'name': tmp_np_name, },
                           'spec': {'podSelector': {'matchLabels': new_label},
                                    'policyTypes': ['Ingress', 'Egress'], }}

        self.logger.info('taking {} offline by NetworkPolicy {}'.format(self.offline_node, tmp_np_name))
        self.api_net_v1.create_namespaced_network_policy(namespace=DEFAULT_NAMESPACE, body=deny_all_policy)
        self.offline_policy_name = tmp_np_name
        register(self.deactivate)

    def deactivate(self):
        self.logger.info('deleting NetworkPolicy {}'.format(self.offline_policy_name))
        self.api_net_v1.delete_namespaced_network_policy(namespace=DEFAULT_NAMESPACE,
                                                         name=self.offline_policy_name)

    offline_node: Optional[Node] = None
    offline_label_key: Optional[str] = None
    offline_policy_name: Optional[str] = None

    def __init__(self, chaos_manager: ChaosManager, node_type: Union[str, Type[Node]], **kwargs) -> None:
        super().__init__(chaos_manager=chaos_manager, **kwargs)
        self.node_type = node_type


class NetworkPartition(ChaosOperator):
    def activate(self):
        raise NotImplementedError()

    def deactivate(self):
        raise NotImplementedError()

    @property
    def can_activate(self) -> bool:
        raise NotImplementedError()

    @property
    def can_deactivate(self) -> bool:
        raise NotImplementedError()
