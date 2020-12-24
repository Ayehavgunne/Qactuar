import multiprocessing
from typing import Dict

from qactuar import ASGIApp, Config
from qactuar.servers.base import BaseQactuarServer


class PreForkServer(BaseQactuarServer):
    def __init__(
        self,
        host: str = None,
        port: int = None,
        app: ASGIApp = None,
        config: Config = None,
    ):
        super().__init__(host, port, app, config)
        self.queues: Dict[int, multiprocessing.Queue] = {}
        self.current_process = 0

    def serve_forever(self) -> None:
        for i in range(self.config.PROCESS_POOL_SIZE or 1):
            self.processes[i] = multiprocessing.Process()
            self.queues[i] = multiprocessing.Queue()
