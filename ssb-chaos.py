from functools import partial
from typing import Type, List

from kubernetes import client, config

from test_template import TestAction
from test_template.actions import BashAction
from test_template.chaos import ChaosManager, Up
from test_template.chaos.operators import NodeOffline
from test_template.mixins import NetworkingV1ApiMixin

from ssb import CopyBuildSsb, SsbDbAndTable, SsbLoadData, SsbQuery, SsbTest


class SsbChaosTest(NetworkingV1ApiMixin, SsbTest):
    def test_actions(self) -> List[Type[TestAction]]:
        return [
            CopyBuildSsb,
            SsbDbAndTable,
            partial(
                Up,
                chaos_operator=NodeOffline(
                    ChaosManager(self.env_instance),
                    node_type='pd',
                    api_net_v1=self.api_net_v1)),
            SsbLoadData,
            SsbQuery,
            BashAction,
        ]


if __name__ == '__main__':
    config.load_kube_config()
    SsbChaosTest(api_core_v1=client.CoreV1Api(),
                 api_apps_v1=client.AppsV1Api(),
                 api_net_v1=client.NetworkingV1Api()).start()
