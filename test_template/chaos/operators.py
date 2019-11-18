from atexit import register, unregister
from random import choice
from typing import Optional, Dict, List, Tuple

from . import ChaosOperator, ChaosManager
from .. import Node, DEFAULT_NAMESPACE, pop_random, NodeType, update_label, get_label
from ..mixins import NetworkingV1ApiMixin, LoggerMixin

"""
Operator class: A kind of actions
Operator instance: one action can be executed during test, can have multiple instance in one test.
"""


class NodeOffline(NetworkingV1ApiMixin, LoggerMixin, ChaosOperator):
    @property
    def can_activate(self) -> bool:
        return self.offline_node is None

    def activate(self):
        assert self.can_activate
        nodes = sum(self._mgr.env.node_instances.values(), [])

        # todo: abstract node selection
        same_type_node = [n for n in nodes if n.is_type(self.node_type)]
        assert same_type_node, 'no nodes of type {}'.format(self.node_type)
        self.offline_node = pop_random(same_type_node)

        old_labels: Dict[str, str] = get_label(self.offline_node)
        self.offline_label_key = 'random-offline-label_{}_0'.format(hash(self))

        new_label = {self.offline_label_key: '0_{}_0'.format(hash(self))}
        old_labels.update(new_label)
        update_label(self.offline_node, old_labels)

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
        labels = get_label(self.offline_node)
        labels.pop(self.offline_label_key)
        update_label(self.offline_node, labels)
        self.offline_label_key = None
        self.offline_node = None
        self.offline_policy_name = None
        unregister(self.deactivate)

    offline_node: Optional[Node] = None
    offline_label_key: Optional[str] = None
    offline_policy_name: Optional[str] = None

    def __init__(self, chaos_manager: ChaosManager, node_type: NodeType, **kwargs) -> None:
        super().__init__(chaos_manager=chaos_manager, **kwargs)
        self.node_type = node_type


class NetworkPartition(NetworkingV1ApiMixin, LoggerMixin, ChaosOperator):
    def activate(self):
        self.regions = ([], [])

        for (node_cls, node_list) in self._mgr.env.node_instances.items():
            node_list: List[Node] = node_list.copy()
            itm = pop_random(node_list)
            if itm is not None:
                self.regions[0].append(itm)
            while node_list:
                choice([r for r in self.regions]).append(pop_random(node_list))

        self.region_label_key = 'random-offline-label_{}_0'.format(hash(self))
        self.region_policy_names = tuple(['np-region-{}-{}'.format(hash(self), i) for i in [0, 1]])
        for ri in (0, 1):
            region = self.regions[ri]

            matched_label = {self.region_label_key: str(ri)}

            for n in region:
                labels = get_label(n)
                labels.update(matched_label)
                update_label(n, labels)

            network_policy_peer = [{'ipBlock': {'cidr': '{}/32'.format(i.pod_ip)}} for i in region]

            region_policy = {'apiVersion': 'networking.k8s.io/v1',
                             'kind': 'NetworkPolicy',
                             'metadata': {'name': self.region_policy_names[ri], },
                             'spec': {
                                 'podSelector': {'matchLabels': matched_label},
                                 'policyTypes': ['Ingress', 'Egress'],
                                 'ingress': [{'from': network_policy_peer}],
                                 'egress': [{'to': network_policy_peer}], }}

            self.logger.info('applying region on {} by {}'.format(region, format(self.region_policy_names[ri])))
            resp = self.api_net_v1.create_namespaced_network_policy(namespace=DEFAULT_NAMESPACE, body=region_policy)
        register(self.deactivate)

    def deactivate(self):
        # activate is not atomic (or fast enough), so there may be some inconsistency
        try:
            for i in (0, 1):
                self.logger.info('deleting region on {}'.format(self.regions[i]))
                self.api_net_v1.delete_namespaced_network_policy(namespace=DEFAULT_NAMESPACE,
                                                                 name=self.region_policy_names[i])
            for ns in self._mgr.env.node_instances.values():
                for n in ns:
                    labels = get_label(n)
                    labels.pop(self.region_label_key)
                    update_label(n, labels)
            self.regions = None
            self.region_label_key = None
            self.region_policy_names = None
            unregister(self.deactivate)
        except Exception as e:
            # self.logger.debug('exception when deactivating:')
            # self.logger.exception(e)
            pass

    @property
    def can_activate(self) -> bool:
        return self.regions is None

    regions: Optional[Tuple[List[Node], List[Node]]] = None
    region_label_key: Optional[str] = None
    region_policy_names: Optional[Tuple[str, str]] = None

    def __init__(self, chaos_manager: ChaosManager, **kwargs) -> None:
        super().__init__(chaos_manager=chaos_manager, **kwargs)
