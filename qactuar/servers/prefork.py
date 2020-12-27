import multiprocessing
from typing import Dict

from qactuar import ASGIApp, Config
from qactuar.processes.prefork import make_child
from qactuar.servers.base import BaseQactuarServer


class PreForkServer(BaseQactuarServer):
    def __init__(
        self,
        host: str = None,
        port: int = None,
        app: ASGIApp = None,
        config: Config = None,
    ):
        self.queues: Dict[int, multiprocessing.Queue] = {}
        self.current_process = 0
        super().__init__(host, port, app, config)

    def serve_forever(self) -> None:
        for i in range(self.config.PROCESS_POOL_SIZE or 1):
            self.queues[i] = multiprocessing.Queue()
            self.processes[i] = multiprocessing.Process(
                target=make_child, args=(self, self.queues[i])
            )
        while True:
            pass
