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
        super().__init__(host, port, app, config)
        self.queues: Dict[int, multiprocessing.Queue] = {}
        self.current_process = 0

    async def serve_forever(self) -> None:
        for i in range(self.config.PROCESS_POOL_SIZE or 1):
            self.queues[i] = multiprocessing.Queue()
            self.processes[i] = multiprocessing.Process(
                target=make_child, args=(self, self.queues[i])
            )
            self.processes[i].daemon = True
            self.processes[i].start()
        while True:
            await self.select_socket()
            if self.shutting_down:
                break

    async def select_socket(self) -> None:
        ready_to_read = await self.loop.run_in_executor(None, self.watch_socket)
        if ready_to_read:
            self.queues[self.current_process].put_nowait(True)
            self.next_process()

    def next_process(self) -> None:
        if self.current_process >= len(self.processes) - 1:
            self.current_process = 0
        else:
            self.current_process += 1
