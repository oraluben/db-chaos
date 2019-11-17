from . import Test, TestAction


class SleepAction(TestAction):
    def __init__(self, test_instance: 'Test', sleep_interval: int, **kwargs) -> None:
        super().__init__(test_instance, **kwargs)
        self.interval = sleep_interval

    def run_action(self):
        from time import sleep
        sleep(self.interval)


class BashAction(TestAction):
    def run_action(self):
        from subprocess import run
        run(['bash'])
