import multiprocessing
import select
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

    def serve_forever(self) -> None:
        self.start_up()
        for i in range(self.config.PROCESS_POOL_SIZE or 1):
            self.queues[i] = multiprocessing.Queue()
            self.processes[i] = multiprocessing.Process(
                target=make_child, args=(self, self.queues[i])
            )
            self.processes[i].daemon = True
            self.processes[i].start()
        try:
            while True:
                self.select_socket()
        except KeyboardInterrupt:
            self.shut_down()
        except Exception as err:
            self.exception_log.exception(err)
            self.shut_down()

    def select_socket(self) -> None:
        ready_to_read, _, _ = select.select(
            [self.listen_socket], [], [], self.config.SELECT_SLEEP_TIME
        )
        if ready_to_read:
            self.queues[self.current_process].put_nowait(True)
            self.next_process()

    def next_process(self) -> None:
        if self.current_process >= len(self.processes) - 1:
            self.current_process = 0
        else:
            self.current_process += 1
