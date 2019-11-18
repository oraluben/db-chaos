from abc import ABC
from random import choice, random
from threading import Thread
from time import sleep
from typing import Optional, List

from test_template import TestBed, TestAction, Test, LoggerMixin


class ChaosOperator(ABC):
    _mgr: 'ChaosManager'

    def __init__(self, chaos_manager: 'ChaosManager', **kwargs) -> None:
        super().__init__(**kwargs)
        self._mgr = chaos_manager

    def activate(self):
        raise NotImplementedError()

    def deactivate(self):
        raise NotImplementedError()

    @property
    def can_activate(self) -> bool:
        raise NotImplementedError()

    @property
    def can_deactivate(self) -> bool:
        # default use neg self.can_activate
        return not self.can_activate


class ChaosManager(LoggerMixin):
    def __iadd__(self, op):
        assert isinstance(op, ChaosOperator)
        self.add_chaos_operator(op)
        return self

    def __isub__(self, op):
        assert isinstance(op, ChaosOperator)
        self.remove_chaos_operator(op)
        return self

    def add_chaos_operator(self, op: ChaosOperator):
        assert op not in self.ops
        self.ops.append(op)

    def remove_chaos_operator(self, op: ChaosOperator):
        idx = self.ops.index(op)
        removed = self.ops.pop(idx)
        if removed.can_deactivate:
            removed.deactivate()

    _singleton: Optional['ChaosManager'] = None
    polling_interval = 10

    def __new__(cls, *args, **kwargs):
        if cls._singleton is None:
            cls._singleton = super().__new__(cls)
            cls._singleton.__init__(*args, **kwargs)
        return cls._singleton

    running: bool = False
    ops: List[ChaosOperator]

    def __init__(self, env: TestBed, start=True) -> None:
        super().__init__()

        self.worker = Thread(target=self.main)
        self.ops = []

        self.env = env

        if start:
            self.start()
        else:
            self.running = False
            self.logger.info('waiting for chaos worker to terminate')
            self.worker.join()

    # Create a thread to trigger chaos operations

    def start(self):
        self.worker.start()

    def stop(self):
        assert self.running
        self.running = False

    def main(self):
        self.running = True
        self.logger.info('chaos worker start')
        while self.running:
            trigger_rate = 0.5
            if self.ops and trigger_rate < random():
                op: ChaosOperator = choice(self.ops)
                if op.can_activate:
                    self.logger.info('activating {}'.format(op))
                    op.activate()
                elif op.can_deactivate:
                    self.logger.info('deactivating {}'.format(op))
                    op.deactivate()
                else:
                    self.logger.error('{} cannot be activated or deactivated, looks like there\'s an inconsistency.')

            sleep(self.polling_interval)

        self.logger.info('chaos worker end')


class ChaosAction(TestAction, ABC):
    """
    Monitor chaos actions
    """

    _mgr: Optional[ChaosManager] = None
    operator: ChaosOperator

    @classmethod
    def set_manager(cls, manager: ChaosManager):
        cls._mgr = manager

    def __new__(cls, test_instance: Test, manager=None, **kwargs) -> 'ChaosAction':
        if cls._mgr is None:
            cls.set_manager(ChaosManager(env=test_instance.env_instance))
        return super().__new__(cls)

    def __init__(self, test_instance: 'Test', chaos_operator: ChaosOperator, **kwargs) -> None:
        super().__init__(test_instance, **kwargs)
        self.operator = chaos_operator


class Up(ChaosAction):
    def run_action(self):
        self._mgr.add_chaos_operator(self.operator)


class Down(ChaosAction):
    def run_action(self):
        self._mgr.remove_chaos_operator(self.operator)
